"""Turn the raw block sample + market data into every number shown on the dashboard.

Reads  data/raw/{sampled_blocks,events}.jsonl, data/raw/account_code.json,
       data/raw/day_heights.json, data/raw/near_price.json, data/raw/stable_supply_*.json,
       labels/known_accounts.json
Writes site/data.json (dashboard), data/processed/*.csv, data/processed/summary.json
"""
import csv, datetime as dt, json, math, os, random, statistics, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, TOKENS

RAW = os.path.join(ROOT, "data", "raw")
PROC = os.path.join(ROOT, "data", "processed")
CATS = ["dex", "intents", "defi", "bridge", "cex", "other_contract", "p2p"]
CAT_NAMES = {"dex": "DEX (Rhea/Ref, Veax)", "intents": "NEAR Intents", "defi": "Lending / perps",
             "bridge": "Bridges", "cex": "Exchanges (labeled)", "other_contract": "Other contracts",
             "p2p": "Wallet-to-wallet"}
BUCKETS = [(0, 1, "<$1"), (1, 10, "$1-10"), (10, 100, "$10-100"), (100, 1e3, "$100-1K"),
           (1e3, 1e4, "$1K-10K"), (1e4, 1e5, "$10K-100K"), (1e5, float("inf"), "$100K+")]
TRADING = {"dex", "intents", "defi"}


def load_jsonl(p):
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs); i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def pearson(a, b):
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    sa = math.sqrt(sum((x - ma) ** 2 for x in a)); sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa and sb else float("nan")


def spearman(a, b):
    return pearson(rank(a), rank(b))


def analyze_intents(days, span, sampled, bday, w):
    """Exploratory (not pre-registered): stablecoin flows inside the NEAR Intents ledger."""
    meta = json.load(open(os.path.join(ROOT, "labels", "intents_stablecoins.json")))["tokens"]
    dec = {t["assetId"]: t["decimals"] for t in meta}
    chain = {t["assetId"]: t["blockchain"] for t in meta}
    recs, seen = [], set()
    for r in load_jsonl(os.path.join(RAW, "intents_events.jsonl")):
        if (r["h"], r["rid"]) in seen or bday.get(r["h"]) not in span: continue
        seen.add((r["h"], r["rid"])); r["day"] = bday[r["h"]]; recs.append(r)
    amt = lambda tid, a: abs(int(a)) / 10 ** dec[tid]
    # solver heuristic: named solver-* accounts, or accounts that settle token_diff without a referral >= 5 times
    nonref = Counter()
    for r in recs:
        for e in r["events"]:
            if e.get("standard") == "dip4" and e.get("event") == "token_diff":
                for d in e["data"]:
                    if "referral" not in d: nonref[d["account_id"]] += 1
    solvers = {a for a, k in nonref.items() if k >= 5} | {a for a in nonref if a.startswith("solver")}
    # hubs: accounts seen in >= 10 sampled Intents stablecoin events (~3,000+ events over the window at
    # this sample rate). Solvers, market makers, 1Click deposit hubs and trading venues, not people.
    seen_n = Counter()
    for r in recs:
        for e in r["events"]:
            if e.get("standard") == "dip4" and e.get("event") in ("transfer", "token_diff"):
                for d in e["data"]:
                    seen_n[d.get("account_id")] += 1
                    if d.get("receiver_id"): seen_n[d["receiver_id"]] += 1
    solvers |= {a for a, k in seen_n.items() if k >= 10}
    is_solver = lambda a: a in solvers or (a or "").startswith("solver")
    flows = []  # (day, type, usd, chain, extra)
    for r in recs:
        for e in r["events"]:
            st, ev = e.get("standard"), e.get("event")
            data = e.get("data") if isinstance(e.get("data"), list) else []
            if st == "dip4" and ev == "token_diff":
                for d in data:
                    pos = sum(amt(t, a) for t, a in d.get("diff", {}).items() if t in dec and int(a) > 0)
                    neg = sum(amt(t, a) for t, a in d.get("diff", {}).items() if t in dec and int(a) < 0)
                    ch = next((chain[t] for t in d.get("diff", {}) if t in dec), None)
                    if max(pos, neg): flows.append((r["day"], "swap", max(pos, neg) / 2, ch, r["h"]))
            elif st == "dip4" and ev == "transfer":
                for d in data:
                    for t, a in d.get("tokens", {}).items():
                        if t not in dec: continue
                        kind = "to_solver" if is_solver(d.get("receiver_id")) or is_solver(d.get("account_id")) else "peer_transfer"
                        flows.append((r["day"], kind, amt(t, a), chain[t], r["h"], d.get("account_id"), d.get("receiver_id"), int(a) % 10 ** dec[t] == 0))
            elif st == "nep245" and ev in ("mt_mint", "mt_burn"):
                for d in data:
                    for t, a in zip(d.get("token_ids", []), d.get("amounts", [])):
                        if t in dec:
                            flows.append((r["day"], "deposit" if ev == "mt_mint" else "withdrawal", amt(t, a), chain[t], r["h"]))
    types = ["swap", "to_solver", "peer_transfer", "deposit", "withdrawal"]
    names = {"swap": "Swaps (stablecoin leg)", "to_solver": "Transfers to solvers / market makers", "peer_transfer": "Peer transfers",
             "deposit": "Deposits into Intents", "withdrawal": "Withdrawals out of Intents"}
    daily = []
    for d in days:
        row = {"day": d}
        for t in types:
            xs = [f for f in flows if f[0] == d and f[1] == t]
            row["n_" + t] = len(xs) * w[d]; row["v_" + t] = sum(f[2] for f in xs) * w[d]
        daily.append(row)
    weekly = defaultdict(lambda: defaultdict(float))
    for r in daily:
        dd = dt.date.fromisoformat(r["day"]); wk = (dd - dt.timedelta(days=dd.weekday())).isoformat()
        for t in types: weekly[wk]["v_" + t] += r["v_" + t]; weekly[wk]["n_" + t] += r["n_" + t]
        weekly[wk]["days"] += 1
    weekly = [{"week": k, **v} for k, v in sorted(weekly.items()) if v["days"] == 7]
    tot = {t: sum(f[2] for f in flows if f[1] == t) for t in types}
    cnt = {t: sum(1 for f in flows if f[1] == t) for t in types}
    chains = Counter()
    for f in flows:
        if f[1] in ("deposit", "withdrawal", "swap"): chains[f[3]] += f[2]
    peers = [f for f in flows if f[1] == "peer_transfer"]
    pamts = sorted(f[2] for f in peers)
    avgd = lambda k: statistics.fmean(r[k] for r in daily)
    out = {
        "types": types, "names": names, "daily": daily, "weekly": weekly,
        "receipts_observed": len(recs), "flows_observed": cnt, "volume_share": {t: tot[t] / sum(tot.values()) for t in types} if sum(tot.values()) else {},
        "avg_daily_volume": {t: avgd("v_" + t) for t in types}, "avg_daily_count": {t: avgd("n_" + t) for t in types},
        "chain_volume_share": {k: v / sum(chains.values()) for k, v in chains.most_common()} if chains else {},
        "peer_median_usd": statistics.median(pamts) if pamts else None,
        "peer_under_100_share": sum(1 for a in pamts if a < 100) / len(pamts) if pamts else None,
        "peer_round_share": (sum(1 for f in peers if f[7] and f[2] >= 1) / sum(1 for f in peers if f[2] >= 1)) if any(f[2] >= 1 for f in peers) else None,
        "peer_unique_senders": len({f[5] for f in peers}), "peer_unique_receivers": len({f[6] for f in peers}),
        "solver_accounts_detected": len(solvers), "hub_rule": "solver-* name, 5+ token_diff without referral, or 10+ sampled Intents stablecoin events",
        "corr_vs_abs_return": None,
    }
    return out


def main():
    labels_doc = json.load(open(os.path.join(ROOT, "labels", "known_accounts.json")))
    exact = {a["account"]: a["category"] for a in labels_doc["accounts"] if "account" in a}
    suffix = [(a["suffix"], a["category"]) for a in labels_doc["accounts"] if "suffix" in a]
    code = json.load(open(os.path.join(RAW, "account_code.json"))) if os.path.exists(os.path.join(RAW, "account_code.json")) else {}

    def acat(a):
        if a in exact: return exact[a]
        for s, c in suffix:
            if a.endswith(s): return c
        if code.get(a) == "contract": return "other_contract"
        return "user"

    blocks = list({b["h"]: b for b in load_jsonl(os.path.join(RAW, "sampled_blocks.jsonl"))}.values())
    seen, events = set(), []
    for e in load_jsonl(os.path.join(RAW, "events.jsonl")):  # dedupe (resumed runs)
        k = (e["h"], e["rid"], e["ev"], e["from"], e["to"], e["amt"])
        if k not in seen:
            seen.add(k); events.append(e)
    fetched = {b["h"] for b in blocks}
    events = [e for e in events if e["h"] in fetched]
    heights = json.load(open(os.path.join(RAW, "day_heights.json")))
    hk = sorted(heights)
    span = {hk[i]: heights[hk[i + 1]] - heights[hk[i]] for i in range(len(hk) - 1)}
    sampled = Counter(b["day"] for b in blocks)
    bday = {b["h"]: b["day"] for b in blocks}
    days = sorted(d for d in sampled if d in span)

    tx = []  # ft_transfer events with derived fields
    mint = defaultdict(float); burn = defaultdict(float)
    for e in events:
        d = bday.get(e["h"])
        if d not in span: continue
        usd = int(e["amt"]) / 10 ** TOKENS[e["token"]]["decimals"]
        if e["ev"] == "ft_mint": mint[d] += usd; continue
        if e["ev"] == "ft_burn": burn[d] += usd; continue
        cf, ct = acat(e["from"]), acat(e["to"])
        cat = "p2p"
        for c in CATS[:-1]:
            if c == "other_contract":
                if "other_contract" in (cf, ct): cat = c; break
            elif c in (cf, ct): cat = c; break
        tx.append({**e, "day": d, "usd": usd, "cat": cat, "cf": cf, "ct": ct})

    w = {d: span[d] / sampled[d] for d in days}  # expansion factor per sampled block
    n = len(tx)
    tot_vol = sum(t["usd"] for t in tx)

    # ---- daily estimates
    daily = []
    for d in days:
        row = {"day": d, "sampled_blocks": sampled[d], "blocks": span[d]}
        for c in CATS:
            xs = [t for t in tx if t["day"] == d and t["cat"] == c]
            row["n_" + c] = len(xs) * w[d]; row["v_" + c] = sum(t["usd"] for t in xs) * w[d]
        row["n_all"] = sum(row["n_" + c] for c in CATS); row["v_all"] = sum(row["v_" + c] for c in CATS)
        row["mint"] = mint[d] * w[d]; row["burn"] = burn[d] * w[d]
        daily.append(row)

    # bootstrap 95% CI for average daily transfers / volume (resample blocks within day)
    per_block = defaultdict(lambda: [0, 0.0, 0, 0.0])
    for t in tx:
        pb = per_block[t["h"]]; pb[0] += 1; pb[1] += t["usd"]
        if t["cat"] == "p2p": pb[2] += 1; pb[3] += t["usd"]
    by_day_blocks = defaultdict(list)
    for b in blocks:
        if b["day"] in span: by_day_blocks[b["day"]].append(per_block.get(b["h"], [0, 0.0, 0, 0.0]))
    rng = random.Random(7); boots = []
    for _ in range(300):
        s = [0.0] * 4
        for d in days:
            bl = by_day_blocks[d]; k = len(bl)
            for _ in range(k):
                pb = bl[rng.randrange(k)]
                for i in range(4): s[i] += pb[i] * w[d]
        boots.append([x / len(days) for x in s])
    def ci(i):
        xs = sorted(b[i] for b in boots); return [xs[int(0.025 * len(xs))], xs[int(0.975 * len(xs)) - 1]]
    avg = lambda key: statistics.fmean(r[key] for r in daily)

    # ---- size distribution
    size = {c: [0] * len(BUCKETS) for c in ["all"] + CATS}
    sizev = {c: [0.0] * len(BUCKETS) for c in ["all"] + CATS}
    for t in tx:
        for i, (lo, hi, _) in enumerate(BUCKETS):
            if lo <= t["usd"] < hi:
                for c in ("all", t["cat"]): size[c][i] += 1; sizev[c][i] += t["usd"]
                break
    med = lambda xs: statistics.median(xs) if xs else None
    amounts = sorted(t["usd"] for t in tx)
    p2p_amounts = sorted(t["usd"] for t in tx if t["cat"] == "p2p")

    # ---- concentration: share of volume in top 1% / 10% of transfers
    def top_share(xs, q):
        xs = sorted(xs, reverse=True); k = max(1, int(len(xs) * q)); s = sum(xs)
        return sum(xs[:k]) / s if s else None
    def gini(xs):
        xs = sorted(xs); m = len(xs); s = sum(xs)
        return (2 * sum((i + 1) * x for i, x in enumerate(xs)) / (m * s) - (m + 1) / m) if s else None
    # accounts: share of sampled volume by top 10 senders
    sv = Counter()
    for t in tx: sv[t["from"]] += t["usd"]
    top_senders = [{"account": a, "usd": v, "share": v / tot_vol, "type": acat(a)} for a, v in sv.most_common(15)]
    pv = Counter()
    for t in tx:
        for a in (t["from"], t["to"]): pv[a] += t["usd"]
    top_parties = [{"account": a, "usd": v, "share_of_transfers_volume": v / tot_vol, "type": acat(a)} for a, v in pv.most_common(25)]

    # ---- round-dollar amounts (invoices / payroll / remittances tend to be round)
    def round_share(ts):
        ts = [t for t in ts if t["usd"] >= 1]
        return sum(1 for t in ts if int(t["amt"]) % 10 ** TOKENS[t["token"]]["decimals"] == 0) / len(ts) if ts else None
    roundness = {c: round_share([t for t in tx if t["cat"] == c]) for c in CATS}
    roundness["all"] = round_share(tx)

    # ---- weekday vs weekend
    def wk_ratio(key):
        we = [r[key] for r in daily if dt.date.fromisoformat(r["day"]).weekday() >= 5]
        wd = [r[key] for r in daily if dt.date.fromisoformat(r["day"]).weekday() < 5]
        return statistics.fmean(we) / statistics.fmean(wd) if we and wd and statistics.fmean(wd) else None

    # ---- price
    price = {dt.datetime.fromtimestamp(p[0] / 1000, dt.timezone.utc).strftime("%Y-%m-%d"): p[1]
             for p in json.load(open(os.path.join(RAW, "near_price.json")))["data"]["prices"]}
    pdays = [r for r in daily if r["day"] in price]
    prev = {}
    for i, d in enumerate(sorted(price)):
        if i: prev[d] = sorted(price)[i - 1]
    absret = {d: abs(math.log(price[d] / price[prev[d]])) for d in prev}
    corr = {}
    for key in ["n_all", "v_all", "n_p2p", "v_p2p", "n_dex", "v_dex", "n_intents", "v_intents"]:
        xs = [r for r in pdays if r["day"] in absret]
        corr[key] = {"vs_abs_return": spearman([r[key] for r in xs], [absret[r["day"]] for r in xs]),
                     "vs_price": spearman([r[key] for r in pdays], [price[r["day"]] for r in pdays])}

    # ---- supply (DefiLlama)
    def supply(name):
        out = {}
        for p in json.load(open(os.path.join(RAW, f"stable_supply_{name}.json")))["data"]:
            d = dt.datetime.fromtimestamp(int(p["date"]), dt.timezone.utc).strftime("%Y-%m-%d")
            out[d] = p["totalCirculatingUSD"]["peggedUSD"]
        return out
    sup = {k: supply(k) for k in ["total", "usdt", "usdc"]}
    sdays = sorted(d for d in sup["total"] if d >= "2025-11-01")
    sup_series = [{"day": d, "total": sup["total"].get(d), "usdt": sup["usdt"].get(d), "usdc": sup["usdc"].get(d),
                   "near": price.get(d)} for d in sdays]
    win_sup = [sup["total"][d] for d in days if d in sup["total"]]

    # ---- weekly composition
    weekly = defaultdict(lambda: defaultdict(float))
    for r in daily:
        wkey = (dt.date.fromisoformat(r["day"]) - dt.timedelta(days=dt.date.fromisoformat(r["day"]).weekday())).isoformat()
        for c in CATS:
            weekly[wkey]["n_" + c] += r["n_" + c]; weekly[wkey]["v_" + c] += r["v_" + c]
        weekly[wkey]["days"] += 1
    weekly = [{"week": k, **v} for k, v in sorted(weekly.items()) if v["days"] == 7]

    share_n = {c: sum(1 for t in tx if t["cat"] == c) / n for c in CATS}
    share_v = {c: sum(t["usd"] for t in tx if t["cat"] == c) / tot_vol for c in CATS}
    cv_daily = statistics.pstdev([r["n_all"] for r in daily]) / avg("n_all")
    cv_p2p = statistics.pstdev([r["n_p2p"] for r in daily]) / avg("n_p2p") if avg("n_p2p") else None
    tok = Counter(); tokv = Counter()
    for t in tx: tok[TOKENS[t["token"]]["symbol"]] += 1; tokv[TOKENS[t["token"]]["symbol"]] += t["usd"]

    # ---- sensitivity (not a pre-registered test): drop wallets seen in >= 10 sampled transfers
    wcount = Counter()
    for t in tx:
        for a, ca in ((t["from"], t["cf"]), (t["to"], t["ct"])):
            if ca == "user": wcount[a] += 1
    hubs = {a for a, k in wcount.items() if k >= 10}
    p2p_strict = [t for t in tx if t["cat"] == "p2p" and t["from"] not in hubs and t["to"] not in hubs]
    big = max(tx, key=lambda t: t["usd"])
    rest = [t for t in tx if t is not big]; rest_v = sum(t["usd"] for t in rest)
    sensitivity_big = {"largest_transfer_usd": big["usd"], "largest_transfer_from": big["from"], "largest_transfer_to": big["to"],
                       "largest_transfer_tx": big["tx"], "largest_transfer_share_of_sampled_volume": big["usd"] / tot_vol,
                       "share_of_volume_excl_largest": {c: sum(t["usd"] for t in rest if t["cat"] == c) / rest_v for c in CATS},
                       "trading_share_excl_largest": sum(t["usd"] for t in rest if t["cat"] in TRADING) / rest_v}
    sensitivity = {"largest": sensitivity_big, "high_frequency_wallets": len(hubs),
                   "p2p_strict_share_of_transfers": len(p2p_strict) / n,
                   "p2p_strict_share_of_volume": sum(t["usd"] for t in p2p_strict) / tot_vol,
                   "rule": "wallet-to-wallet transfers where neither wallet appears in 10+ sampled transfers"}

    # ---- pre-registered tests (thresholds fixed in THESIS.md before the data was pulled)
    trading_v = sum(share_v[c] for c in TRADING)
    tests = [
        {"id": "T1", "name": "Small tickets", "rule": "Median transfer under $100 and at least half of transfers under $100",
         "value": f"median ${med(amounts):,.2f}; {sum(1 for a in amounts if a < 100) / n:.0%} under $100",
         "pass": med(amounts) < 100 and sum(1 for a in amounts if a < 100) / n >= 0.5},
        {"id": "T2", "name": "Wallet-to-wallet use", "rule": "At least 40% of transfers are wallet-to-wallet (no contract on either side)",
         "value": f"{share_n['p2p']:.1%} of transfers", "pass": share_n["p2p"] >= 0.40},
        {"id": "T3", "name": "Not trading-dominated", "rule": "DEX + Intents + lending/perps carry under 50% of volume",
         "value": f"{trading_v:.1%} of volume", "pass": trading_v < 0.5},
        {"id": "T4", "name": "Decoupled from volatility", "rule": "|Spearman rho| between daily volume and NEAR |daily return| under 0.3",
         "value": f"rho = {corr['v_all']['vs_abs_return']:.2f}", "pass": abs(corr["v_all"]["vs_abs_return"]) < 0.3},
        {"id": "T5", "name": "Broad-based value", "rule": "Largest 1% of transfers carry under 50% of volume",
         "value": f"{top_share(amounts, 0.01):.1%} of volume", "pass": top_share(amounts, 0.01) < 0.5},
        {"id": "T6", "name": "Steady flow", "rule": "Coefficient of variation of daily transfer count under 0.5",
         "value": f"CV = {cv_daily:.2f}", "pass": cv_daily < 0.5},
    ]
    summary = {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window": {"start": days[0], "end": days[-1], "days": len(days)},
        "sample": {"blocks_sampled": sum(sampled[d] for d in days), "blocks_in_window": sum(span[d] for d in days),
                   "sample_rate": sum(sampled[d] for d in days) / sum(span[d] for d in days),
                   "transfers_observed": n, "mints_burns_observed": sum(1 for e in events if e["ev"] != "ft_transfer"),
                   "accounts_observed": len(pv), "volume_observed_usd": tot_vol},
        "estimates": {"avg_daily_transfers": avg("n_all"), "avg_daily_transfers_ci95": ci(0),
                      "avg_daily_volume_usd": avg("v_all"), "avg_daily_volume_ci95": ci(1),
                      "avg_daily_p2p_transfers": avg("n_p2p"), "avg_daily_p2p_transfers_ci95": ci(2),
                      "avg_daily_p2p_volume_usd": avg("v_p2p"), "avg_daily_p2p_volume_ci95": ci(3)},
        "share_of_transfers": share_n, "share_of_volume": share_v, "trading_share_of_volume": trading_v,
        "median_transfer_usd": med(amounts), "median_p2p_transfer_usd": med(p2p_amounts),
        "under_100_share": sum(1 for a in amounts if a < 100) / n,
        "p2p_under_100_share": sum(1 for a in p2p_amounts if a < 100) / len(p2p_amounts) if p2p_amounts else None,
        "top1pct_transfer_volume_share": top_share(amounts, 0.01), "top10pct_transfer_volume_share": top_share(amounts, 0.10),
        "gini_transfer_size": gini(amounts), "top_senders": top_senders, "top_counterparties": top_parties,
        "round_dollar_share": roundness, "weekend_to_weekday": {k: wk_ratio(k) for k in ["n_all", "n_p2p", "n_dex", "n_intents"]},
        "cv_daily_transfers": cv_daily, "cv_daily_p2p": cv_p2p, "correlations": corr,
        "tokens": {k: {"transfers": tok[k] / n, "volume": tokv[k] / tot_vol} for k in tok},
        "supply": {"start": win_sup[0] if win_sup else None, "end": win_sup[-1] if win_sup else None,
                   "latest": sup_series[-1] if sup_series else None},
        "price": {"start": price.get(days[0]), "end": price.get(days[-1])},
        "velocity_daily": avg("v_all") / statistics.fmean(win_sup) if win_sup else None,
        "tests": tests, "passed": sum(t["pass"] for t in tests), "sensitivity": sensitivity,
    }
    intents = analyze_intents(days, span, sampled, bday, w)
    xs = [r for r in intents["daily"] if r["day"] in absret]
    if xs:
        tot_i = lambda r: sum(r["v_" + t] for t in intents["types"])
        intents["corr_vs_abs_return"] = {
            "all": spearman([tot_i(r) for r in xs], [absret[r["day"]] for r in xs]),
            "peer_transfer": spearman([r["v_peer_transfer"] for r in xs], [absret[r["day"]] for r in xs]),
            "swap": spearman([r["v_swap"] for r in xs], [absret[r["day"]] for r in xs])}
    try:
        ll = json.load(open(os.path.join(RAW, "intents_volume_defillama.json")))["data"]["totalDataChart"]
        llv = {dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"): v for t, v in ll}
        xs = [llv[d] for d in days if d in llv]
        intents["defillama_avg_daily_volume"] = statistics.fmean(xs) if xs else None
        intents["swap_vs_defillama"] = intents["avg_daily_volume"]["swap"] / intents["defillama_avg_daily_volume"] if xs else None
    except FileNotFoundError:
        intents["defillama_avg_daily_volume"] = None
    summary["intents"] = {k: v for k, v in intents.items() if k not in ("daily", "weekly")}
    os.makedirs(PROC, exist_ok=True)
    with open(os.path.join(PROC, "intents_daily_estimates.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(intents["daily"][0].keys())); wr.writeheader(); wr.writerows(intents["daily"])
    with open(os.path.join(PROC, "daily_estimates.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(daily[0].keys()) + ["near_usd"]); wr.writeheader()
        for r in daily: wr.writerow({**r, "near_usd": price.get(r["day"])})
    with open(os.path.join(PROC, "transfers_sample.csv"), "w", newline="") as f:
        wr = csv.writer(f); wr.writerow(["block", "day", "token", "from", "to", "usd", "category", "methods", "tx"])
        for t in tx: wr.writerow([t["h"], t["day"], TOKENS[t["token"]]["symbol"], t["from"], t["to"], round(t["usd"], 6), t["cat"], "|".join(t["methods"]), t["tx"]])
    json.dump(summary, open(os.path.join(PROC, "summary.json"), "w"), indent=1)
    site = {"summary": summary, "daily": daily, "weekly": weekly, "supply": sup_series, "cats": CATS, "cat_names": CAT_NAMES,
            "buckets": [b[2] for b in BUCKETS], "intents": intents, "size": size, "size_volume": sizev, "labels_source": "labels/known_accounts.json"}
    json.dump(site, open(os.path.join(ROOT, "site", "data.json"), "w"), separators=(",", ":"))
    print(json.dumps({k: summary[k] for k in ["window", "sample", "estimates", "share_of_transfers", "share_of_volume", "median_transfer_usd", "passed", "intents"]}, indent=1))
    for t in tests: print(t["id"], t["pass"], t["value"])


if __name__ == "__main__":
    main()
