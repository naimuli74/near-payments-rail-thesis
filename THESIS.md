# THESIS: Is NEAR already a payments rail?

Track: Investment Thesis (`thesis`), NEAR HACKATHON. Data window 2026-08-15 to 2026-11-12 UTC. Generated 2026-11-14T02:05:26Z from [`data/processed/summary.json`](data/processed/summary.json).

## 1. Claim being tested

> Stablecoin activity on NEAR already behaves like a payments network rather than a trading venue.

Why an investor should care: a chain that carries payments earns durable, price-insensitive usage (fees, storage, account growth) that does not disappear in a bear market. A chain whose stablecoins mostly feed DEX arbitrage has usage that tracks speculation. The two deserve different multiples.

## 2. Metrics and pre-registered tests

The six tests below were committed in [PREREGISTRATION.md](PREREGISTRATION.md) before the analysis ran. All six passing means "payments rail".

| id | test | pass rule | measured | result |
| --- | --- | --- | --- | --- |
| T1 | Small tickets | Median transfer under $100 and at least half of transfers under $100 | median $138.19; 40% under $100 | **FAIL** |
| T2 | Wallet-to-wallet use | At least 40% of transfers are wallet-to-wallet (no contract on either side) | 2.3% of transfers | **FAIL** |
| T3 | Not trading-dominated | DEX + Intents + lending/perps carry under 50% of volume | 29.5% of volume | **PASS** |
| T4 | Decoupled from volatility | |Spearman rho| between daily volume and NEAR |daily return| under 0.3 | rho = 0.26 | **PASS** |
| T5 | Broad-based value | Largest 1% of transfers carry under 50% of volume | 79.8% of volume | **FAIL** |
| T6 | Steady flow | Coefficient of variation of daily transfer count under 0.5 | CV = 0.63 | **FAIL** |

**Score: 2 / 6. Verdict: Not yet. NEAR stablecoins mostly move like a trading venue, not a payments network.**

Robustness check (reported, not re-scored): one sampled transfer of $2.5M to `nfendowment02.near` is 59% of sampled volume. Excluding it, DEX + Intents + lending carry 72% of volume (T3 would read FAIL). We keep the pre-registered scoring as computed and show this so readers can judge it.

## 3. Evidence for the thesis

- Wallet-to-wallet transfers look like payments: median $49.98, 59% under $100, and 29.6% are whole-dollar amounts versus 4.5% for DEX legs.
- Wallet-to-wallet volume barely tracks NEAR volatility (Spearman rho -0.01 vs absolute daily return), while DEX volume does (0.28).
- About 1,242 wallet-to-wallet stablecoin transfers a day (95% CI 981 to 1,460) is a real, non-zero base.
- Stablecoin supply on NEAR (DefiLlama) is $133.4M as of 2026-11-14.
- NEAR Intents moves other chains' dollars at scale: about $55.4M deposited and $54.5M withdrawn a day in the sample, across 19 chains (eth 50%, tron 17%, arb 14%, base 9%). NEAR is acting as a settlement layer for stablecoins it did not issue.

## 4. Evidence against the thesis

- 93% of stablecoin transfers touch a DEX, which is a trading venue's profile. By dollars, DEX + Intents + lending carry 30% of sampled volume, or 72% once the single largest transfer is set aside.
- Wallet-to-wallet transfers are only 2.3% of transfers and 10.0% of dollars.
- The overall median transfer is $138.19; only 40% of transfers are under $100.
- Value is concentrated: the largest 1% of transfers carry 80% of volume (top 10%: 89%).
- Total daily volume co-moves with NEAR volatility (rho 0.26), and the daily transfer count is volatile (CV 0.63).
- Inside Intents, swaps and solver transfers outnumber peer transfers: swap legs are about 57,888 a day against 4,163 peer transfers.

## 5. What would change our mind

We would call NEAR a payments rail if, re-running this exact pipeline on a later quarter:

- Wallet-to-wallet share of volume rises from 10.0% to above 25% for a full quarter.
- DEX + Intents + lending share of volume falls below 50% even with the single largest transfer set aside (now 30% overall, 72% without it).
- Daily stablecoin volume stops tracking NEAR volatility (|rho| below 0.3; now 0.26).
- Round-dollar transfers (invoices, payroll) grow as a share of all transfers (now 5.5%).
- Peer transfers inside NEAR Intents grow to a meaningful share of Intents stablecoin flow (now 1.6% of sampled Intents stablecoin volume).

And we would drop even the "payments layer exists" part if wallet-to-wallet transfers turned out to be mostly exchange or bot wallets once they are labeled.

## 6. Investment implication

Do not underwrite NEAR as a payments network today. The data shows a trading venue with a small but real payments layer: $5.6M a day of wallet-to-wallet stablecoin flow with consumer-sized tickets, sitting on a growing stablecoin base ($131.2M). The long-term bet is optionality: if that layer's share of volume grows, the thesis flips. This dashboard is the tripwire, and anyone can re-run it.

Practical read: treat NEAR today as a **cross-chain settlement and trading venue with a small payments layer**, not as a payments chain. The cheap, falsifiable signal to watch is the wallet-to-wallet share of stablecoin volume together with peer transfers inside NEAR Intents. The dashboard recomputes both from raw blocks, so the thesis can be re-checked every quarter.

## 7. Reproducibility

Everything above comes from `npm run build-data` (or `npm run quick` from the committed snapshot; `make all` / `make quick` do the same). The block sample is seeded, the label lists cite their sources, and `scripts/spot_check.py` re-verifies random sampled transfers against an archival node. See the README for steps and limitations.
