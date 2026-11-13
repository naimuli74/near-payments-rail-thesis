"""Daily NEAR price (CoinGecko) and stablecoin supply on NEAR (DefiLlama). Free, no key."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, http_json

OUT = os.path.join(ROOT, "data", "raw")
SOURCES = {
    "near_price": "https://api.coingecko.com/api/v3/coins/near/market_chart?vs_currency=usd&days=180&interval=daily",
    "stable_supply_total": "https://stablecoins.llama.fi/stablecoincharts/Near",
    "stable_supply_usdt": "https://stablecoins.llama.fi/stablecoincharts/Near?stablecoin=1",
    "stable_supply_usdc": "https://stablecoins.llama.fi/stablecoincharts/Near?stablecoin=2",
    "intents_volume_defillama": "https://api.llama.fi/summary/dexs/near-intents?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true",
}

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, url in SOURCES.items():
        d = http_json(url)
        json.dump({"source": url, "data": d}, open(os.path.join(OUT, name + ".json"), "w"))
        print(name, "ok")
