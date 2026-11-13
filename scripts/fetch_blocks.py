"""Stratified random sample of NEAR mainnet blocks from neardata.xyz (FASTNEAR, free, no key).

For each UTC day in the window we draw N block heights uniformly at random (seeded, so the
sample is identical on every machine), download each full block, and keep every successful
NEP-141 event (ft_transfer / ft_mint / ft_burn) emitted by the stablecoin contracts.

Resumable: already-fetched heights are skipped. Rate-limited to stay under neardata's
documented 180 requests/minute/IP.

Usage: python3 scripts/fetch_blocks.py [--days 90] [--per-day 480] [--end 2026-11-13]
"""
import argparse, datetime as dt, json, os, random, socket, sys, threading, time
socket.setdefaulttimeout(30)
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, TOKENS, NEARDATA, http_json, height_at, block_ts

VERSION = 2  # v2 also records NEAR Intents (intents.near) stablecoin events
INTENTS = "intents.near"
STABLE_IDS = {t["assetId"] for t in json.load(open(os.path.join(ROOT, "labels", "intents_stablecoins.json")))["tokens"]}
STABLE_STR = tuple(i.split(":", 1)[1] if i.startswith("nep141:") else i for i in STABLE_IDS)

RAW = os.path.join(ROOT, "data", "raw")
SEED = 20261114


def day_bounds(args):
    end = dt.datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    start = end - dt.timedelta(days=args.days)
    path = os.path.join(RAW, "day_heights.json")
    cache = json.load(open(path)) if os.path.exists(path) else {}
    days = [(start + dt.timedelta(days=i)) for i in range(args.days + 1)]
    lo = 150_000_000
    from common import rpc
    head = int(rpc("block", {"finality": "final"})["header"]["height"])
    for d in days:
        k = d.strftime("%Y-%m-%d")
        if k not in cache:
            cache[k] = height_at(int(d.timestamp() * 1e9), lo, head)
            print("day", k, "starts at height", cache[k], flush=True)
            json.dump(cache, open(path, "w"), indent=1)
        lo = cache[k]
    keys = [d.strftime("%Y-%m-%d") for d in days]
    return [(keys[i], cache[keys[i]], cache[keys[i + 1]]) for i in range(args.days)]


class Bucket:
    def __init__(self, rate):
        self.rate, self.lock, self.next = rate, threading.Lock(), time.monotonic()
    def take(self):
        with self.lock:
            now = time.monotonic()
            wait = self.next - now
            self.next = max(now, self.next) + 1.0 / self.rate
        if wait > 0:
            time.sleep(wait)


def fetch_block(url, retries=6):
    """curl with a hard --max-time: some long-lived HTTPS connections stall mid-body and Python's
    per-recv socket timeout never fires, so each block is fetched by a fresh curl process."""
    import subprocess
    delay = 2
    for attempt in range(retries):
        p = subprocess.run(["curl", "-sL", "--compressed", "--max-time", "40", "-A", "near-payments-rail-thesis",
                            "-w", "\n%{http_code}", url], capture_output=True, text=True)
        body, _, code = p.stdout.rpartition("\n")
        if p.returncode == 0 and code == "200":
            return json.loads(body)
        print("retry", code or p.returncode, url[-12:], flush=True)
        time.sleep(delay); delay = min(delay * 2, 60)
    raise RuntimeError("failed " + url)


def extract_intents(height, ts, o):
    """Keep intents.near receipts whose events mention a stablecoin asset id."""
    oc = o["execution_outcome"]["outcome"]
    if "Failure" in (oc.get("status") or {}):
        return None
    evs = []
    for log in oc.get("logs", []):
        if not log.startswith("EVENT_JSON:") or not any(x in log for x in STABLE_STR):
            continue
        try:
            evs.append(json.loads(log[len("EVENT_JSON:"):]))
        except Exception:
            pass
    if not evs:
        return None
    rc = o.get("receipt") or {}
    act = (rc.get("receipt") or {}).get("Action") or {}
    methods = [a["FunctionCall"].get("method_name") for a in act.get("actions", []) if isinstance(a, dict) and "FunctionCall" in a]
    return {"h": height, "ts": ts, "rid": rc.get("receipt_id"), "tx": o.get("tx_hash"), "pred": rc.get("predecessor_id"),
            "signer": act.get("signer_id"), "methods": methods, "events": evs}


def extract(height, blk):
    out = []
    intents = []
    ts = int(blk["block"]["header"]["timestamp"])
    for sh in blk.get("shards", []):
        for o in sh.get("receipt_execution_outcomes") or []:
            oc = o["execution_outcome"]["outcome"]
            ex = oc["executor_id"]
            if ex == INTENTS:
                r = extract_intents(height, ts, o)
                if r:
                    intents.append(r)
                continue
            if ex not in TOKENS:
                continue
            if "Failure" in (oc.get("status") or {}):
                continue
            rc = o.get("receipt") or {}
            act = (rc.get("receipt") or {}).get("Action") or {}
            methods = []
            for a in act.get("actions", []):
                if isinstance(a, dict) and "FunctionCall" in a:
                    methods.append(a["FunctionCall"].get("method_name"))
            for log in oc.get("logs", []):
                if not log.startswith("EVENT_JSON:"):
                    continue
                try:
                    ev = json.loads(log[len("EVENT_JSON:"):])
                except Exception:
                    continue
                if ev.get("standard") != "nep141":
                    continue
                for i, d in enumerate(ev.get("data", [])):
                    e = ev.get("event")
                    if e == "ft_transfer":
                        frm, to = d.get("old_owner_id"), d.get("new_owner_id")
                    elif e == "ft_mint":
                        frm, to = None, d.get("owner_id")
                    elif e == "ft_burn":
                        frm, to = d.get("owner_id"), None
                    else:
                        continue
                    out.append({
                        "h": height, "ts": ts, "token": ex, "ev": e, "from": frm, "to": to,
                        "amt": d.get("amount"), "memo": d.get("memo"),
                        "pred": rc.get("predecessor_id"), "signer": act.get("signer_id"),
                        "methods": methods, "tx": o.get("tx_hash"), "rid": rc.get("receipt_id"),
                    })
    return ts, out, intents


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--per-day", type=int, default=480)
    ap.add_argument("--end", default="2026-11-13", help="exclusive end date (UTC)")
    ap.add_argument("--rate", type=float, default=2.6, help="requests per second")
    ap.add_argument("--passes", type=int, default=4, help="interleave days in this many passes")
    args = ap.parse_args()
    os.makedirs(RAW, exist_ok=True)
    days = day_bounds(args)
    done_path = os.path.join(RAW, "sampled_blocks.jsonl")
    ev_path = os.path.join(RAW, "events.jsonl")
    done = set()
    if os.path.exists(done_path):
        for line in open(done_path):
            r = json.loads(line)
            if r.get("v") == VERSION:
                done.add(r["h"])
    plan = []
    for day, h0, h1 in days:
        rng = random.Random(f"{SEED}:{day}")
        hs = rng.sample(range(h0, h1), args.per_day)
        plan.append((day, hs))
    jobs = []
    step = args.per_day // args.passes
    for p in range(args.passes):
        for day, hs in plan:
            for h in hs[p * step:(p + 1) * step]:
                if h not in done:
                    jobs.append((day, h))
    print(f"{len(jobs)} blocks to fetch ({len(done)} cached)", flush=True)
    # Download with parallel curl processes (xargs), ingest finished files as they land.
    # Each worker sleeps between requests so the total stays under the documented 180 req/min.
    import subprocess, glob as G, urllib.request as ur
    base = NEARDATA
    try:
        with ur.urlopen(ur.Request(f"{NEARDATA}/v0/block/{jobs[0][1]}/headers", headers={"User-Agent": "near-payments-rail-thesis"}), timeout=30) as r:
            u = r.geturl(); base = u[:u.index("/v0/")]
    except Exception:
        pass
    print("archive host", base, flush=True)
    tmp = os.path.join(RAW, "_dl"); os.makedirs(tmp, exist_ok=True)
    dayof = dict((h, d) for d, h in jobs)
    with open(os.path.join(tmp, "_jobs.txt"), "w") as f:
        for d, h in jobs:
            f.write(f"{h}\n")
    workers = max(1, int(args.rate * 3))  # ~1 s per request + 2 s pause per worker
    cmd = (f"xargs -P {workers} -I@ sh -c 'curl -sL --compressed --max-time 40 -A near-payments-rail-thesis "
           f"-o {tmp}/@.part -w \"%{{http_code}}\" {base}/v0/block/@ > {tmp}/@.code; "
           f"[ \"$(cat {tmp}/@.code)\" = 200 ] && mv {tmp}/@.part {tmp}/@.json; rm -f {tmp}/@.code {tmp}/@.part; sleep 2' < {tmp}/_jobs.txt")
    proc = subprocess.Popen(cmd, shell=True)
    fd, fe = open(done_path, "a"), open(ev_path, "a")
    fi = open(os.path.join(RAW, "intents_events.jsonl"), "a")
    stats = {"n": 0, "ev": 0}

    def ingest():
        for fpath in G.glob(os.path.join(tmp, "*.json")):
            h = int(os.path.basename(fpath)[:-5])
            try:
                blk = json.load(open(fpath))
            except Exception:
                os.remove(fpath); continue
            day = dayof.get(h)
            if blk is None:
                rec, evs, ins = {"h": h, "day": day, "missing": True, "v": VERSION}, [], []
            else:
                ts, evs, ins = extract(h, blk)
                rec = {"h": h, "day": day, "ts": ts, "n": len(evs), "ni": len(ins), "v": VERSION}
            for e in evs: fe.write(json.dumps(e) + "\n")
            for e in ins: fi.write(json.dumps(e) + "\n")
            fd.write(json.dumps(rec) + "\n")
            fd.flush(); fe.flush(); fi.flush()
            os.remove(fpath)
            stats["n"] += 1; stats["ev"] += len(evs)
            if stats["n"] % 200 == 0:
                print(time.strftime("%H:%M:%S"), stats, flush=True)

    while proc.poll() is None:
        ingest(); time.sleep(5)
    ingest()
    fd.close(); fe.close(); fi.close()
    print("done", stats)


if __name__ == "__main__":
    main()
