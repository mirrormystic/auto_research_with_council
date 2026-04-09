---
target_file: strategy.sol
reference_files:
  - AMMStrategyBase.sol
  - IAMMStrategy.sol
validate: "uv run amm-match validate strategy.sol"
eval: "uv run amm-match run strategy.sol"
metric_regex: "Edge: ([\\d.]+)"
direction: maximize
---

# AMM Fee Strategy Optimization

## The Problem

You are optimizing a dynamic fee strategy for a constant-product AMM (x * y = k) in a simulated market. Your strategy competes against a fixed 30bps AMM for order flow.

Two types of traders interact with your AMM:

1. **Retail traders** — arrive randomly (Poisson, rate lambda ~ U[0.6, 1.0] per step), trade random sizes (LogNormal with sigma=1.2, mean ~ U[19, 21] in Y terms). You profit from their fees. 50% buy, 50% sell.

2. **Arbitrage bots** — exploit price differences between your AMM's spot price and the true market price. You lose to them. They trade the profit-maximizing amount using closed-form CFMM formulas.

Orders are split optimally between your AMM and the 30bps competitor to equalize marginal execution prices. The router formula: A_i = sqrt(x_i * gamma_i * y_i), flow proportional to A_i.

## Simulation Structure

Each simulation runs 10,000 steps. Per step, in order:
1. Price moves via GBM: S(t+1) = S(t) * exp(-sigma^2/2 + sigma*Z), Z ~ N(0,1)
2. Arbitrageur trades on EACH AMM independently (if profitable)
3. Retail orders arrive (Poisson) and are routed optimally across AMMs

Key: afterSwap is called after EACH trade (arb or retail). The fee you return applies to the NEXT trade, not the current one.

## Parameters

- Per-step sigma ~ U[0.000882, 0.001008], zero drift
- Initial reserves: X=100, Y=10,000, price=100
- 1000 simulations per evaluation with randomized parameters
- Fees are fee-on-input (Uniswap V2 style)
- Fees collected separately, NOT reinvested into liquidity (V3/V4 style)
- k = x * y is conserved across trades

## Scoring: Edge

Edge measures profit/loss vs the true asset price:
- AMM buys X: edge = amountX * truePrice - amountY
- AMM sells X: edge = amountY - amountX * truePrice

Retail trades generate positive edge. Arb trades generate negative edge. Total edge is summed across all trades in all simulations. Higher = better.

## What You Submit

A Solidity contract (^0.8.24) inheriting AMMStrategyBase with two functions:

```solidity
function afterInitialize(uint256 initialX, uint256 initialY)
    external returns (uint256 bidFee, uint256 askFee)

function afterSwap(TradeInfo calldata trade)
    external returns (uint256 bidFee, uint256 askFee)
```

TradeInfo fields:
- bool isBuy — true if AMM bought X (trader sold X to you)
- uint256 amountX — amount of X traded (WAD precision, 1e18)
- uint256 amountY — amount of Y traded (WAD precision, 1e18)
- uint256 timestamp — simulation step number (0-9999)
- uint256 reserveX — post-trade X reserves (WAD)
- uint256 reserveY — post-trade Y reserves (WAD)

## Constraints

- Fees: 0 to 1000 bps. WAD format (1e18 = 100%). Use bpsToWad(30) for 30bps.
- Gas: 250,000 per function call
- Storage: 32 uint256 slots only (slots[0]-slots[31]), accessed via readSlot/writeSlot
- No assembly, external calls, new contracts, or oracles
- Contract must be named "Strategy" and inherit AMMStrategyBase

## Available Helpers (from AMMStrategyBase)

- wmul(x, y), wdiv(x, y) — WAD multiplication/division
- bpsToWad(bps), wadToBps(wad) — conversion
- clampFee(fee) — clamp to [0, MAX_FEE] (10%)
- clamp(value, min, max), absDiff(a, b), sqrt(x)
- readSlot(i), writeSlot(i, value) — storage access (0-31)

## Benchmarks

Baseline (flat 30bps): ~344 edge
Leaderboard leaders: ~522 edge

## Key Insights From Prior Research

- Optimal FIXED fee is ~75bps (NOT 30bps). Fee sweep data:
  5bps=78, 10=161, 20=286, 30=348, 50=375, 75=386, 100=381
- Best dynamic so far: 10bps calm + 100bps spike via vol EMA + 10bps directional asymmetry = 406
- Asymmetric bid/ask (charge more on arb-likely side) adds ~8 points
- EMA of |ratio change| is the best vol proxy found so far
- Trade size signal is weak (router splits orders, muddies the signal)
- Timestamp-based arb/retail detection fails (~45% of steps have 0 retail)
- Curve shape (linear vs sqrt vs quadratic ramp) barely matters (<5 pts)
- Dual EMA (fast+slow) hurts — don't raise floor during volatile regimes
- The gap from 406 to 522 likely requires a fundamentally different approach
