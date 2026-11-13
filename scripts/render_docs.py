"""Write README.md and THESIS.md from data/processed/summary.json so every number in the docs
matches the dashboard. Usage: python3 scripts/render_docs.py"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT

S = json.load(open(os.path.join(ROOT, "data", "processed", "summary.json")))
N = json.load(open(os.path.join(ROOT, "site", "narrative.json")))
LIVE = "https://near.darkhouse.online"
MIRROR = "https://near-payments-rail.tasnovanaime.workers.dev"
REPO = "https://github.com/naimuli74/near-payments-rail-thesis"


def usd(x):
    if x is None: return "n/a"
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(x) >= div: return f"${x / div:,.1f}{suf}"
    return f"${x:,.2f}"


pct = lambda x, d=0: "n/a" if x is None else f"{x * 100:.{d}f}%"
E, I, sv, sn = S["estimates"], S["intents"], S["share_of_volume"], S["share_of_transfers"]
c = S["correlations"]
SB = S["sensitivity"]["largest"]
win = S["window"]; smp = S["sample"]
tests_md = "\n".join(f"| {t['id']} | {t['name']} | {t['rule']} | {t['value']} | **{'PASS' if t['pass'] else 'FAIL'}** |" for t in S["tests"])
top_chain = list(I["chain_volume_share"].items())[:4]
chains_txt = ", ".join(f"{k} {pct(v)}" for k, v in top_chain)
iv, ic = I["avg_daily_volume"], I["avg_daily_count"]
ivs = I["volume_share"]
verdict = N["verdict"]

headline = f"""- {smp['transfers_observed']:,} USDC/USDT transfers observed in {smp['blocks_sampled']:,} randomly sampled mainnet blocks ({pct(smp['sample_rate'], 2)} of all blocks), {win['start']} to {win['end']} UTC.
- About **{E['avg_daily_transfers']:,.0f} stablecoin transfers a day** on NEAR (95% CI {E['avg_daily_transfers_ci95'][0]:,.0f} to {E['avg_daily_transfers_ci95'][1]:,.0f}), moving about **{usd(E['avg_daily_volume_usd'])} a day** (95% CI {usd(E['avg_daily_volume_ci95'][0])} to {usd(E['avg_daily_volume_ci95'][1])}).
- **{pct(sn['dex'])} of transfers involve a DEX** (Rhea/Ref). DEX + NEAR Intents + lending carry {pct(S['trading_share_of_volume'])} of sampled volume ({pct(SB['trading_share_excl_largest'])} excluding the single largest transfer, see robustness below).
- **Wallet-to-wallet transfers are {pct(sn['p2p'], 1)} of transfers and {pct(sv['p2p'], 1)} of volume**, but they look like payments: median {usd(S['median_p2p_transfer_usd'])}, {pct(S['p2p_under_100_share'])} under $100.
- Daily volume vs NEAR's absolute daily return: Spearman rho = {c['v_all']['vs_abs_return']:.2f} overall, {c['v_dex']['vs_abs_return']:.2f} for DEX flow, {c['v_p2p']['vs_abs_return']:.2f} for wallet-to-wallet flow.
- Exploratory: inside NEAR Intents, about **{usd(iv['deposit'])} a day of stablecoins is deposited and {usd(iv['withdrawal'])} withdrawn**, mostly dollars from other chains ({chains_txt}). Stablecoin peer transfers inside Intents: about {ic['peer_transfer']:,.0f} a day, median {usd(I['peer_median_usd'])}.
- Robustness: a single sampled transfer of {usd(SB['largest_transfer_usd'])} (to `{SB['largest_transfer_to']}`, [tx](https://nearblocks.io/txns/{SB['largest_transfer_tx']})) is {pct(SB['largest_transfer_share_of_sampled_volume'])} of all sampled dollars. Without it, DEX + Intents + lending carry {pct(SB['trading_share_excl_largest'])} of volume and wallet-to-wallet {pct(SB['share_of_volume_excl_largest']['p2p'])}. Dollar shares are fragile in a block sample; transfer counts are the robust signal.
- Result: **{S['passed']} of 6 pre-registered tests pass.**"""

readme = f"""# Is NEAR already a payments rail?

An evidence-first investment thesis for NEAR, built at **NEAR HACKATHON** (Investment Thesis track, `thesis`).

**Live dashboard:** {LIVE} (mirror: {MIRROR})

## Thesis and verdict

If NEAR is turning into money infrastructure, the stablecoins on it should move like payments: many small transfers between ordinary wallets, a steady daily rhythm, and no dependence on NEAR's price swings. If it is mostly a trading venue, stablecoin flow will run through DEXs and bots and follow volatility. We sampled {smp['blocks_sampled']:,} NEAR mainnet blocks at random over {win['days']} days, pulled every USDC and USDT transfer in them straight from the chain, and scored the flow against six tests that were [committed before the analysis ran](PREREGISTRATION.md).

**Verdict: {verdict}** {S['passed']} of 6 tests pass. The native-token layer is dominated by DEX and bot flow. The payment-shaped activity that does exist is small, and a growing share of NEAR's stablecoin role is happening inside NEAR Intents, where dollars from other chains are deposited, swapped and withdrawn. Full argument in [THESIS.md](THESIS.md).

## Headline numbers

{headline}

All numbers are produced by `scripts/analyze.py` and stored in [`data/processed/summary.json`](data/processed/summary.json). The docs are generated from that file by `scripts/render_docs.py`, so they cannot drift from the data.

## Try it (do X, see Y)

1. **Open {LIVE}.** You see the verdict, the six pass/fail tests, ten charts each with a one-line takeaway and a source line, and a table of the largest counterparties.
2. **Rebuild every number from the committed snapshot, offline, in seconds:**
   ```sh
   git clone {REPO} && cd near-payments-rail-thesis
   npm run quick         # = python3 scripts/analyze.py && node scripts/build_site.mjs && python3 scripts/render_docs.py  (or: make quick)
   ```
   You see the six test results printed (for example `T2 False {S['tests'][1]['value']}`), the same values as the dashboard. `dist/index.html` is the dashboard; serve it with `npm run serve` and open http://localhost:8000.
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
| Stablecoin supply on NEAR | [DefiLlama stablecoins](https://defillama.com/stablecoins/Near) `/stablecoincharts/Near` | `scripts/fetch_market.py` |

## Method

- **Tokens:** native USDC (`17208628f84f5d6ad33f0da3bbbeb27ffcb398eac501a31bd6ad2011e36133a1`), native USDT (`usdt.tether-token.near`), bridged USDC.e and USDT.e (`*.factory.bridge.near`).
- **Sample:** for each UTC day, 480 block heights drawn uniformly at random with a fixed seed (`20261114`), so every machine fetches the same blocks. Every successful NEP-141 `ft_transfer`, `ft_mint` and `ft_burn` event emitted by those contracts is kept, plus `intents.near` events that mention a stablecoin asset id.
- **Estimates:** day total = sample total x (blocks in day / sampled blocks). 95% intervals come from 300 bootstrap resamples of blocks within each day.
- **Counterparty type:** documented labels first ([labels/known_accounts.json](labels/known_accounts.json), each with a source link), then a contract-code check via `view_account` (code hash not all ones = contract). Wallet-to-wallet means neither side has contract code. Priority: DEX > Intents > lending/perps > bridge > exchange > other contract > wallet.
- **Correlations:** Spearman rank correlation between daily estimates and NEAR's absolute daily log return / price level (CoinGecko daily closes).
- **Intents (exploratory, not pre-registered):** `dip4 token_diff` = swap (stablecoin leg, each side counted once), `dip4 transfer` = transfer (to infrastructure, or peer-to-peer), `nep245 mt_mint` / `mt_burn` = deposit / withdrawal. Infrastructure = `solver-*` name, 5+ `token_diff` settlements without a referral tag, or 10+ sampled Intents stablecoin events (at a 0.33% sample that is thousands of events, so not a person).

## Limitations

- It is a {pct(smp['sample_rate'], 2)} block sample, not a census. Heavy-tailed transfer sizes make daily volume noisy; counts are more stable than dollars. Intervals are shown for the main estimates.
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
data/raw/                   snapshot: sampled blocks, events, market data (generated {S['generated_at']})
data/processed/             summary.json, daily_estimates.csv, intents_daily_estimates.csv, transfers_sample.csv
site/                       dashboard template and Chart.js (MIT)
```

## Hackathon disclosure

All code in this repository was written during NEAR HACKATHON (November 2026). Third-party code: Chart.js 4.4.6 (MIT), vendored in `site/vendor/`. AI coding assistants were used. The dashboard is hosted on Cloudflare Workers and will stay up through at least 2026-11-25.

## License

MIT, see [LICENSE](LICENSE). Not investment advice.
"""

thesis = f"""# THESIS: Is NEAR already a payments rail?

Track: Investment Thesis (`thesis`), NEAR HACKATHON. Data window {win['start']} to {win['end']} UTC. Generated {S['generated_at']} from [`data/processed/summary.json`](data/processed/summary.json).

## 1. Claim being tested

> Stablecoin activity on NEAR already behaves like a payments network rather than a trading venue.

Why an investor should care: a chain that carries payments earns durable, price-insensitive usage (fees, storage, account growth) that does not disappear in a bear market. A chain whose stablecoins mostly feed DEX arbitrage has usage that tracks speculation. The two deserve different multiples.

## 2. Metrics and pre-registered tests

The six tests below were committed in [PREREGISTRATION.md](PREREGISTRATION.md) before the analysis ran. All six passing means "payments rail".

| id | test | pass rule | measured | result |
| --- | --- | --- | --- | --- |
{tests_md}

**Score: {S['passed']} / 6. Verdict: {verdict}**

Robustness check (reported, not re-scored): one sampled transfer of {usd(SB['largest_transfer_usd'])} to `{SB['largest_transfer_to']}` is {pct(SB['largest_transfer_share_of_sampled_volume'])} of sampled volume. Excluding it, DEX + Intents + lending carry {pct(SB['trading_share_excl_largest'])} of volume (T3 would read {'PASS' if SB['trading_share_excl_largest'] < 0.5 else 'FAIL'}). We keep the pre-registered scoring as computed and show this so readers can judge it.

## 3. Evidence for the thesis

- Wallet-to-wallet transfers look like payments: median {usd(S['median_p2p_transfer_usd'])}, {pct(S['p2p_under_100_share'])} under $100, and {pct(S['round_dollar_share'].get('p2p'), 1)} are whole-dollar amounts versus {pct(S['round_dollar_share'].get('dex'), 1)} for DEX legs.
- Wallet-to-wallet volume barely tracks NEAR volatility (Spearman rho {c['v_p2p']['vs_abs_return']:.2f} vs absolute daily return), while DEX volume does ({c['v_dex']['vs_abs_return']:.2f}).
- About {E['avg_daily_p2p_transfers']:,.0f} wallet-to-wallet stablecoin transfers a day (95% CI {E['avg_daily_p2p_transfers_ci95'][0]:,.0f} to {E['avg_daily_p2p_transfers_ci95'][1]:,.0f}) is a real, non-zero base.
- Stablecoin supply on NEAR (DefiLlama) is {usd(S['supply']['latest']['total'])} as of {S['supply']['latest']['day']}.
- NEAR Intents moves other chains' dollars at scale: about {usd(iv['deposit'])} deposited and {usd(iv['withdrawal'])} withdrawn a day in the sample, across {len(I['chain_volume_share'])} chains ({chains_txt}). NEAR is acting as a settlement layer for stablecoins it did not issue.

## 4. Evidence against the thesis

- {pct(sn['dex'])} of stablecoin transfers touch a DEX, which is a trading venue's profile. By dollars, DEX + Intents + lending carry {pct(S['trading_share_of_volume'])} of sampled volume, or {pct(SB['trading_share_excl_largest'])} once the single largest transfer is set aside.
- Wallet-to-wallet transfers are only {pct(sn['p2p'], 1)} of transfers and {pct(sv['p2p'], 1)} of dollars.
- The overall median transfer is {usd(S['median_transfer_usd'])}; only {pct(S['under_100_share'])} of transfers are under $100.
- Value is concentrated: the largest 1% of transfers carry {pct(S['top1pct_transfer_volume_share'])} of volume (top 10%: {pct(S['top10pct_transfer_volume_share'])}).
- Total daily volume co-moves with NEAR volatility (rho {c['v_all']['vs_abs_return']:.2f}), and the daily transfer count is volatile (CV {S['cv_daily_transfers']:.2f}).
- Inside Intents, swaps and solver transfers outnumber peer transfers: swap legs are about {ic['swap']:,.0f} a day against {ic['peer_transfer']:,.0f} peer transfers.

## 5. What would change our mind

We would call NEAR a payments rail if, re-running this exact pipeline on a later quarter:

{chr(10).join('- ' + x.replace('<li>', '').replace('</li>', '') for x in N['changelist'].split('</li>') if x.strip())}
- Peer transfers inside NEAR Intents grow to a meaningful share of Intents stablecoin flow (now {pct(ivs.get('peer_transfer'), 1)} of sampled Intents stablecoin volume).

And we would drop even the "payments layer exists" part if wallet-to-wallet transfers turned out to be mostly exchange or bot wallets once they are labeled.

## 6. Investment implication

{N['impl']}

Practical read: treat NEAR today as a **cross-chain settlement and trading venue with a small payments layer**, not as a payments chain. The cheap, falsifiable signal to watch is the wallet-to-wallet share of stablecoin volume together with peer transfers inside NEAR Intents. The dashboard recomputes both from raw blocks, so the thesis can be re-checked every quarter.

## 7. Reproducibility

Everything above comes from `npm run build-data` (or `npm run quick` from the committed snapshot; `make all` / `make quick` do the same). The block sample is seeded, the label lists cite their sources, and `scripts/spot_check.py` re-verifies random sampled transfers against an archival node. See the README for steps and limitations.
"""

open(os.path.join(ROOT, "README.md"), "w").write(readme)
open(os.path.join(ROOT, "THESIS.md"), "w").write(thesis)
print("README.md and THESIS.md written")
