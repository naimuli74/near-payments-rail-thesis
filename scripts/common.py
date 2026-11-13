"""Shared helpers. Standard library only so anyone can re-run with plain python3."""
import json, time, urllib.request, urllib.error, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "near-payments-rail-thesis/1.0 (+https://github.com/naimuli74/near-payments-rail-thesis)"}

# Stablecoin contracts on NEAR mainnet (sources in labels/README.md)
TOKENS = {
    "17208628f84f5d6ad33f0da3bbbeb27ffcb398eac501a31bd6ad2011e36133a1": {"symbol": "USDC", "kind": "native", "decimals": 6},
    "usdt.tether-token.near": {"symbol": "USDT", "kind": "native", "decimals": 6},
    "a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48.factory.bridge.near": {"symbol": "USDC.e", "kind": "bridged", "decimals": 6},
    "dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near": {"symbol": "USDT.e", "kind": "bridged", "decimals": 6},
}

RPC = os.environ.get("NEAR_RPC", "https://archival-rpc.mainnet.fastnear.com")
NEARDATA = os.environ.get("NEARDATA", "https://mainnet.neardata.xyz")


def http_json(url, data=None, retries=6, timeout=60):
    body = json.dumps(data).encode() if data is not None else None
    headers = dict(UA)
    if body is not None:
        headers["Content-Type"] = "application/json"
    delay = 2
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(delay); delay = min(delay * 2, 60); continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt < retries - 1:
                time.sleep(delay); delay = min(delay * 2, 60); continue
            raise


def rpc(method, params):
    try:
        r = http_json(RPC, {"jsonrpc": "2.0", "id": "x", "method": method, "params": params})
    except urllib.error.HTTPError as e:
        if e.code in (400, 422):  # e.g. UNKNOWN_BLOCK for a skipped height
            raise RuntimeError("rpc %s: HTTP %d" % (method, e.code))
        raise
    if "error" in r:
        raise RuntimeError(r["error"])
    return r["result"]


def block_ts(height):
    """Timestamp (ns) of the first existing block at or after height."""
    for h in range(height, height + 50):
        try:
            return h, int(rpc("block", {"block_id": h})["header"]["timestamp"])
        except RuntimeError:
            continue
    raise RuntimeError("no block near %d" % height)


def height_at(ts_ns, lo, hi):
    """Binary search: first block height with timestamp >= ts_ns."""
    while hi - lo > 1:
        mid = (lo + hi) // 2
        _, t = block_ts(mid)
        if t >= ts_ns:
            hi = mid
        else:
            lo = mid
    return hi
