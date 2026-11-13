"""Classify every account seen in the sampled stablecoin events.

1. Documented labels from labels/known_accounts.json (each entry cites a public source).
2. For every other account: NEAR RPC view_account -> does it have contract code deployed?
   (code_hash != 11111111111111111111111111111111 means a smart contract).
Results cached in data/raw/account_code.json so re-runs only query new accounts.
"""
import json, os, sys, threading
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, rpc

EMPTY = "11111111111111111111111111111111"
CACHE = os.path.join(ROOT, "data", "raw", "account_code.json")


def accounts():
    s = set()
    for line in open(os.path.join(ROOT, "data", "raw", "events.jsonl")):
        e = json.loads(line)
        for k in ("from", "to"):
            if e.get(k):
                s.add(e[k])
    return s


def main():
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = sorted(a for a in accounts() if a not in cache)
    print(len(todo), "accounts to check,", len(cache), "cached", flush=True)
    lock = threading.Lock()

    def check(a):
        try:
            r = rpc("query", {"request_type": "view_account", "finality": "final", "account_id": a})
            v = "contract" if r.get("code_hash") != EMPTY else "account"
        except RuntimeError as e:
            v = "deleted_or_missing" if "UNKNOWN_ACCOUNT" in str(e) or "HTTP" in str(e) else "error"
        with lock:
            cache[a] = v
            if len(cache) % 500 == 0:
                json.dump(cache, open(CACHE, "w")); print(len(cache), flush=True)

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(check, todo))
    json.dump(cache, open(CACHE, "w"), indent=0, sort_keys=True)
    print("done", len(cache))


if __name__ == "__main__":
    main()
