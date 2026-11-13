# Rebuild everything from the chain. Python 3.9+ (standard library only) and Node 18+.
.PHONY: all data market labels analyze site
all: data market labels analyze site
data:      ## sample blocks from neardata.xyz (resumable; ~4h at the free rate limit)
	python3 scripts/fetch_blocks.py --days 90 --per-day 480 --end 2026-11-13
market:    ## NEAR price (CoinGecko) + stablecoin supply (DefiLlama)
	python3 scripts/fetch_market.py
labels:    ## contract-code check for every account seen
	python3 scripts/label_accounts.py
analyze:   ## every number on the dashboard -> site/data.json, data/processed/
	python3 scripts/analyze.py
site:      ## static dashboard -> dist/index.html (+ Cloudflare Worker bundle)
	node scripts/build_site.mjs
quick:     ## re-run analysis + site from the committed snapshot (seconds, no network)
	python3 scripts/analyze.py && node scripts/build_site.mjs
