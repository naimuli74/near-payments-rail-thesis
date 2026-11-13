# Is NEAR already a payments rail?

An evidence-first investment thesis for NEAR, built at **NEAR HACKATHON** (Investment Thesis track, `thesis`).

**Live dashboard:** https://near.darkhouse.online (mirror: https://near-payments-rail.tasnovanaime.workers.dev)

## Thesis and verdict

If NEAR is turning into money infrastructure, the stablecoins on it should move like payments: many small transfers between ordinary wallets, a steady daily rhythm, and no dependence on NEAR's price swings. If it is mostly a trading venue, stablecoin flow will run through DEXs and bots and follow volatility. We sampled 7,007 NEAR mainnet blocks at random over 59 days, pulled every USDC and USDT transfer in them straight from the chain, and scored the flow against six tests that were [committed before the analysis ran](PREREGISTRATION.md).

**Verdict: Not yet. NEAR stablecoins mostly move like a trading venue, not a payments network.** 2 of 6 tests pass. The native-token layer is dominated by DEX and bot flow. The payment-shaped activity that does exist is small, and a growing share of NEAR's stablecoin role is happening inside NEAR Intents, where dollars from other chains are deposited, swapped and withdrawn. Full argument in [THESIS.md](THESIS.md).

## Headline numbers

- 2,390 USDC/USDT transfers observed in 7,007 randomly sampled mainnet blocks (0.08% of all blocks), 2026-08-15 to 2026-10-12 UTC.
- About **48,117 stablecoin transfers a day** on NEAR (95% CI 44,849 to 52,166), moving about **$71.9M a day** (95% CI $15.9M to $177.6M).
- **93% of transfers involve a DEX** (Rhea/Ref). DEX + NEAR Intents + lending carry 24% of sampled volume (81% excluding the single largest transfer, see robustness below).
- **Wallet-to-wallet transfers are 2.2% of transfers and 5.3% of volume**, but they look like payments: median $49.98, 58% under $100.
- Daily volume vs NEAR's absolute daily return: Spearman rho = 0.24 overall, 0.28 for DEX flow, 0.10 for wallet-to-wallet flow.
- Exploratory: inside NEAR Intents, about **$67.4M a day of stablecoins is deposited and $48.4M withdrawn**, mostly dollars from other chains (eth 47%, tron 19%, base 12%, arb 10%). Stablecoin peer transfers inside Intents: about 3,554 a day, median $9.95. Cross-check: our stablecoin swap-leg estimate ($48.4M a day) is 34% of DefiLlama's all-asset NEAR Intents volume ($141.3M a day) over the same days.
- Robustness: a single sampled transfer of $2.5M (to `nfendowment02.near`, [tx](https://nearblocks.io/txns/D6MKuMtaNLvoK4vuJyMQWBhEqR5uSc8cnQxpMkq6abZQ)) is 71% of all sampled dollars. Without it, DEX + Intents + lending carry 81% of volume and wallet-to-wallet 18%. Dollar shares are fragile in a block sample; transfer counts are the robust signal.
- Result: **2 of 6 pre-registered tests pass.**

All numbers are produced by `scripts/analyze.py` and stored in [`data/processed/summary.json`](data/processed/summary.json). The docs are generated from that file by `scripts/render_docs.py`, so they cannot drift from the data.

## Try it (do X, see Y)

1. **Open https://near.darkhouse.online.** You see the verdict, the six pass/fail tests, ten charts each with a one-line takeaway and a source line, and a table of the largest counterparties.
2. **Rebuild every number from the committed snapshot, offline, in seconds:**
   ```sh
   git clone https://github.com/naimuli74/near-payments-rail-thesis && cd near-payments-rail-thesis
   npm run quick         # = python3 scripts/analyze.py && node scripts/build_site.mjs && python3 scripts/render_docs.py  (or: make quick)
   ```
   You see the six test results printed (for example `T2 False 2.2% of transfers`), the same values as the dashboard. `dist/index.html` is the dashboard; serve it with `npm run serve` and open http://localhost:8000.
3. **Check that the sample is real chain data:**
   ```sh
   python3 scripts/spot_check.py 5
   ```
   You see 5 random sampled transfers re-fetched from a NEAR archival RPC node, each marked `OK` with a NearBlocks link showing the same sender, receiver and amount.
4. **Re-pull everything from the chain** (no API keys, Python standard library only):
   ```sh
   rm -rf data/raw/*.jsonl data/raw/account_code.json   # optional: start clean
   npm run build-data    # or: make all
   ```
   You see the sampler fetch the same seeded block heights from neardata.xyz. The full plan (480 blocks a day for 90 days) takes about 4.5 hours at the free rate limit of 180 requests a minute. For a 25-minute run, use `python3 scripts/fetch_blocks.py --per-day 40` and expect the shares to land inside the 95% intervals above.

## Data sources

| What | Source | Script |
| --- | --- | --- |
| Full mainnet blocks (receipts, execution outcomes, logs) | [FASTNEAR neardata.xyz](https://github.com/fastnear/neardata-server), free, no key | `scripts/fetch_blocks.py` |
| Day boundaries, contract-code check, spot checks | NEAR archival RPC (`archival-rpc.mainnet.fastnear.com`, [public providers](https://docs.near.org/api/rpc/providers)) | `scripts/common.py`, `label_accounts.py`, `spot_check.py` |
| USDC contract on NEAR | [Circle: USDC contract addresses](https://developers.circle.com/stablecoins/usdc-contract-addresses), [USDC.e vs USDC](https://www.circle.com/blog/usdc-is-now-available-on-near) | `scripts/common.py` |
| USDT contract on NEAR | [Tether supported protocols](https://tether.to/en/supported-protocols) (`usdt.tether-token.near`) | `scripts/common.py` |
| DEX / lending contract ids | [Rhea Finance contracts](https://guide.rhea.finance/developers/contracts) | `labels/known_accounts.json` |
| NEAR Intents stablecoin asset ids | [NEAR Intents 1Click token list](https://1click.chaindefuser.com/v0/tokens) | `labels/intents_stablecoins.json` |
| NEAR price | [CoinGecko](https://www.coingecko.com/en/api) `/coins/near/market_chart` | `scripts/fetch_market.py` |
| NEAR Intents total volume (cross-check only) | [DefiLlama](https://defillama.com/protocol/near-intents) `/summary/dexs/near-intents` | `scripts/fetch_market.py` |
| Stablecoin supply on NEAR | [DefiLlama stablecoins](https://defillama.com/stablecoins/Near) `/stablecoincharts/Near` | `scripts/fetch_market.py` |

## Method

- **Tokens:** native USDC (`17208628f84f5d6ad33f0da3bbbeb27ffcb398eac501a31bd6ad2011e36133a1`), native USDT (`usdt.tether-token.near`), bridged USDC.e and USDT.e (`*.factory.bridge.near`).
- **Sample:** for each UTC day, 480 block heights drawn uniformly at random with a fixed seed (`20261114`), so every machine fetches the same blocks. Every successful NEP-141 `ft_transfer`, `ft_mint` and `ft_burn` event emitted by those contracts is kept, plus `intents.near` events that mention a stablecoin asset id.
- **Estimates:** day total = sample total x (blocks in day / sampled blocks). 95% intervals come from 300 bootstrap resamples of blocks within each day.
- **Counterparty type:** documented labels first ([labels/known_accounts.json](labels/known_accounts.json), each with a source link), then a contract-code check via `view_account` (code hash not all ones = contract). Wallet-to-wallet means neither side has contract code. Priority: DEX > Intents > lending/perps > bridge > exchange > other contract > wallet.
- **Correlations:** Spearman rank correlation between daily estimates and NEAR's absolute daily log return / price level (CoinGecko daily closes).
- **Intents (exploratory, not pre-registered):** `dip4 token_diff` = swap (stablecoin leg, each side counted once), `dip4 transfer` = transfer (to infrastructure, or peer-to-peer), `nep245 mt_mint` / `mt_burn` = deposit / withdrawal. Infrastructure = `solver-*` name, 5+ `token_diff` settlements without a referral tag, or 10+ sampled Intents stablecoin events (at a 0.33% sample that is thousands of events, so not a person).

## Limitations

- It is a 0.08% block sample, not a census. Heavy-tailed transfer sizes make daily volume noisy; counts are more stable than dollars. Intervals are shown for the main estimates.
- Unique-user counts and repeat-counterparty rates are not reported: a block sample cannot estimate them honestly.
- Exchange hot wallets are labeled only where documented. Unlabeled exchange or bot wallets count as wallets, which flatters the payments side.
- Counting NEAR Intents deposits and withdrawals as trading-venue flow is conservative; some of it is cross-chain payments. The Intents section reports it separately.
- Amounts are valued at $1 per stablecoin.
- Before writing the pre-registration we looked at about 200 recent blocks to decide which contracts needed labels. That look showed heavy DEX activity.

## Repository layout

```
scripts/fetch_blocks.py     seeded block sampler (neardata.xyz)
scripts/fetch_market.py     CoinGecko price, DefiLlama supply
scripts/label_accounts.py   contract-code check for every account seen
scripts/analyze.py          all metrics, tests, bootstrap CIs -> site/data.json, data/processed/
scripts/build_site.mjs      dashboard + Cloudflare Worker bundle -> dist/
scripts/render_docs.py      README.md + THESIS.md from summary.json
scripts/spot_check.py       re-verify random sampled transfers on chain
labels/                     documented account labels and stablecoin asset ids, with sources
data/raw/                   snapshot: sampled blocks, events, market data (generated 2026-11-13T20:46:20Z)
data/processed/             summary.json, daily_estimates.csv, intents_daily_estimates.csv, transfers_sample.csv
site/                       dashboard template and Chart.js (MIT)
```

## Hackathon disclosure

All code in this repository was written during NEAR HACKATHON (November 2026). Third-party code: Chart.js 4.4.6 (MIT), vendored in `site/vendor/`. AI coding assistants were used. The dashboard is hosted on Cloudflare Workers and will stay up through at least 2026-11-25.

## License

MIT, see [LICENSE](LICENSE). Not investment advice.
