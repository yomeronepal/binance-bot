# 15m Day-Trade Engine — V3 Baseline

Reference numbers for the current (V2) engine, measured by
`python manage.py backtest_daytrade`. Every V3 entry-quality change is judged
against this baseline.

## Method

- Walk-forward through the live `DayTradeSignalEngine.evaluate()` (no look-ahead:
  trailing windows; the 1h frame only includes candles closed before the signal
  candle).
- Active exit model: fixed-percentage **SL 2.5% / TP 6.0%** (R:R 1:2.4).
- One position per symbol at a time (matches production).
- SL checked before TP within the same candle (conservative).
- Sizing: $100 margin x 10x leverage per trade.

## Run

- Date window: trailing **90 days**
- Symbols: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT
- Config: defaults — `min_score 8.5 / 13.5`, `min_confidence 0.70`

## Baseline result (overall)

| Metric | Value |
| --- | --- |
| Resolved trades | 135 (+4 open) |
| Win rate | 29.63% |
| Breakeven win rate | 29.41% |
| Profit factor | 1.011 |
| Net PnL | +$25.00 |
| Expectancy / trade | +$0.19 |
| Avg win / avg loss | $60.00 / $25.00 |
| Max drawdown | $735.00 |
| Max consecutive losses | 14 |

## Per symbol

| Symbol | Trades | Win % | PF | Net | Max DD | Max consec. losses |
| --- | --- | --- | --- | --- | --- | --- |
| BTCUSDT | 19 | 36.8 | 1.40 | +$120 | $150 | 6 |
| ETHUSDT | 35 | 25.7 | 0.83 | -$110 | $255 | 10 |
| SOLUSDT | 49 | 30.6 | 1.06 | +$50 | $330 | 11 |
| BNBUSDT | 32 | 28.1 | 0.94 | -$35 | $225 | 9 |

## Read

The strategy is essentially **at breakeven** — win rate (29.6%) sits right on the
breakeven line (29.4%), profit factor ~1.0, net PnL ~flat. Only BTC is clearly
profitable; ETH and BNB lose. Tail risk is the standout concern: **14 consecutive
losses** and a $735 drawdown.

This is exactly the gap the V3 entry-quality work targets: lift win rate / profit
factor and cut the losing streaks by filtering low-quality entries.

## Acceptance bar for V3 changes

A change ships only if, vs this baseline on the same window, it improves
**profit factor** (and ideally win rate) without collapsing trade count, and does
not worsen max drawdown / consecutive losses materially.

---

# Task 1 — Market structure (BOS / CHoCH / swing significance / graded quality)

Scoring was refactored so each component contributes `weight * quality`; structure
is now graded (0-1) from significance-filtered swings with a BOS and strong-leg
bonus. Gated behind `structure_quality_enabled` (default off → reproduces V2,
verified). Run with `--structure-v3 --min-swing-atr 0.5` (no hard BOS/CHoCH gates).

## Overall (90d, same 4 symbols)

| Metric | Baseline (V2) | Task 1 (V3) | Delta |
| --- | --- | --- | --- |
| Resolved trades | 135 | 125 | -10 |
| Win rate | 29.63% | 35.20% | +5.6pp |
| Profit factor | 1.011 | **1.304** | +0.29 |
| Net PnL | +$25 | **+$615** | +$590 |
| Max drawdown | $735 | **$465** | -$270 |
| Max consecutive losses | 14 | **10** | -4 |

## Per symbol (Task 1)

| Symbol | Win % | PF | Net | vs baseline net |
| --- | --- | --- | --- | --- |
| BTCUSDT | 44.4 | 1.92 | +$230 | +$110 |
| ETHUSDT | 33.3 | 1.20 | +$120 | +$230 (was -$110) |
| SOLUSDT | 33.3 | 1.20 | +$150 | +$100 |
| BNBUSDT | 34.6 | 1.27 | +$115 | +$150 (was -$35) |

All four symbols are profitable (ETH and BNB flipped from losers), so the gain is
broad-based, not a single-symbol artifact.

## Threshold sweep (`--min-swing-atr`)

| ATR mult | Trades | Win % | PF | Net |
| --- | --- | --- | --- | --- |
| 0.3 | 125 | 35.2 | 1.304 | +$615 |
| 0.5 | 125 | 35.2 | 1.304 | +$615 |
| 0.75 | 128 | 34.4 | 1.257 | +$540 |
| 1.0 | 129 | 32.6 | 1.159 | +$345 |

Sweet spot 0.3-0.5 ATR. Hard CHoCH-block hurt (PF 1.186) and is left off by default.

## Status

Engine + harness only (no DB migration yet, to avoid colliding with the unmerged
futures migration 0055). Recommended live config once wired to the DB + admin:
`structure_quality_enabled=true`, `structure_min_swing_atr=0.5`,
`require_bos=false`, `block_on_choch=false`. Still **paper-only** pending more
out-of-sample validation.
