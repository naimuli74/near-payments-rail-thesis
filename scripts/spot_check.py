"""Pick random sampled transfers and re-verify them against a NEAR archival RPC node.

For each transfer we call EXPERIMENTAL_tx_status on the transaction and confirm that the same
NEP-141 event (sender, receiver, amount) appears in its receipts. Prints a NearBlocks link so a
human can check the same thing in a browser.  Usage: python3 scripts/spot_check.py [N]
"""
import json, os, random, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, TOKENS, rpc

n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
evs = [json.loads(l) for l in open(os.path.join(ROOT, "data", "raw", "events.jsonl"))]
evs = [e for e in evs if e["ev"] == "ft_transfer" and e.get("tx") and e.get("signer")]
ok = 0
for e in random.Random().sample(evs, min(n, len(evs))):
    r = rpc("EXPERIMENTAL_tx_status", {"tx_hash": e["tx"], "sender_account_id": e["signer"], "wait_until": "NONE"})
    found = False
    for ro in r.get("receipts_outcome", []):
        for log in ro["outcome"]["logs"]:
            if log.startswith("EVENT_JSON:") and ro["outcome"]["executor_id"] == e["token"]:
                for d in json.loads(log[11:]).get("data", []):
                    if d.get("old_owner_id") == e["from"] and d.get("new_owner_id") == e["to"] and d.get("amount") == e["amt"]:
                        found = True
    ok += found
    usd = int(e["amt"]) / 10 ** TOKENS[e["token"]]["decimals"]
    print(f"{'OK ' if found else 'MISS'} {TOKENS[e['token']]['symbol']:6} ${usd:,.2f}  {e['from']} -> {e['to']}\n     https://nearblocks.io/txns/{e['tx']}")
print(f"{ok}/{n} sampled transfers re-verified on chain")
