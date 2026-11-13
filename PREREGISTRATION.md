# Pre-registration

Committed before any analysis of the sampled data was run (see this file's git timestamp; the
block sampler had fetched under 1% of its plan when this was written).

## Question

Is stablecoin activity on NEAR already shaped like a payments network, or like a trading venue?

## Data

USDC (Circle, `17208628f84f5d6ad33f0da3bbbeb27ffcb398eac501a31bd6ad2011e36133a1`), USDT (Tether,
`usdt.tether-token.near`) and their Rainbow Bridge versions (USDC.e, USDT.e). NEP-141 `ft_transfer`
events from a seeded random sample of 480 blocks per UTC day, 2026-08-15 to 2026-11-12, plus NEAR
price (CoinGecko) and stablecoin supply (DefiLlama).

## Tests (all six pass = payments rail)

| id | name | pass rule |
| --- | --- | --- |
| T1 | Small tickets | median transfer < $100 and >= 50% of transfers < $100 |
| T2 | Wallet-to-wallet use | >= 40% of transfers have no contract on either side |
| T3 | Not trading-dominated | DEX + NEAR Intents + lending/perps carry < 50% of volume |
| T4 | Decoupled from volatility | abs(Spearman rho) between daily volume and NEAR abs(daily log return) < 0.3 |
| T5 | Broad-based value | the largest 1% of transfers carry < 50% of volume |
| T6 | Steady flow | coefficient of variation of daily transfer count < 0.5 |

Verdict mapping: 5-6 pass = "Yes", 3-4 = "Partly", 0-2 = "Not yet".

Counting NEAR Intents deposits/withdrawals as trading-venue flow is a deliberate, conservative choice
that biases against the thesis. It is reported separately so readers can re-weight it.
