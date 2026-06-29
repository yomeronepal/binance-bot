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
