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

## Multi-window validation (the honest picture)

The 90d gain did NOT generalize. Across three windows (BTC/ETH/SOL/BNB,
min-swing 0.5, no hard gates):

| Window | Baseline PF | V3 PF | Baseline net | V3 net | V3 vs base |
| --- | --- | --- | --- | --- | --- |
| 90d | 1.011 | 1.304 | +$25 | +$615 | clearly better |
| 120d | 0.985 | 1.084 | -$50 | +$260 | better |
| 180d | 1.312 | 1.287 | +$1585 | +$1485 | slightly worse |

On 180d V3 also worsened tail risk (max DD $775 -> $1260, consec losses 13 -> 16),
and per-symbol it was roughly a wash. So V3 filters help in weaker recent periods
but add nothing (and hurt drawdown) over the longer window.

## Verdict: INCONCLUSIVE — not shipped

Task 1 is **not** a validated edge. It stays **off by default**
(`structure_quality_enabled=False`), so the live engine is unchanged. The
scoring refactor is retained (it is faithful: reproduces V2 exactly when the flag
is off) as the foundation for further experiments. No DB migration / admin wiring
until a variant demonstrates a robust, multi-window improvement.

Open follow-ups: try structure quality as an *additive* bonus on top of full base
weight (rather than scaling the base down), validate with non-overlapping
walk-forward windows and a wider symbol set, and reassess BOS/CHoCH as booster
signals rather than gates.

---

# Part 3 + revised Task 1 — walk-forward validation

Added walk-forward comparison to the harness:
`backtest_daytrade --compare --segments N` runs baseline vs V3 over the same
fetched data and reports per-segment profit factor / net plus a segment win tally.
This judges a change across many non-overlapping windows instead of one.

Two structure designs were retested this way (additive: full base weight + a
separate `weight_structure_bonus` for BOS/strong-leg confluence; the base weight
is never scaled down):

## 180d / 6 segments

| Config | PF | Net | Win% | Max DD | Consec L | Segments won |
| --- | --- | --- | --- | --- | --- | --- |
| Baseline | 1.312 | $1585 | 35.4 | $775 | 13 | - |
| V3 additive (bonus 1.0) | 1.327 | $1700 | 35.6 | $990 | 17 | 3/6 |
| V3 significance-gate only (bonus 0) | **1.386** | **$1990** | **36.6** | $820 | 13 | **5/6** |

## 270d / 9 segments (significance-gate only)

| Config | PF | Net | Win% | Max DD | Consec L | Segments won |
| --- | --- | --- | --- | --- | --- | --- |
| Baseline | 1.154 | $1315 | 32.5 | $910 | 19 | - |
| V3 significance-gate only | 1.183 | $1605 | 33.0 | $1045 | 19 | 6/9 |

## Revised verdict

- The **swing-significance filter** (ignore legs smaller than `min_swing_atr*ATR`
  when reading structure direction) is a **modest but robust edge**: it wins the
  majority of walk-forward segments in both 180d and 270d and improves PF + net in
  every window tested, with drawdown roughly flat-to-slightly-worse.
- The **BOS / strong-leg confluence bonus** is **not** helpful (it diluted strong
  trends and worsened drawdown). Left in the code but defaulted to
  `weight_structure_bonus = 0.0`.

Recommended config when this is wired to the DB + admin (still off by default
until then; paper-only): `structure_quality_enabled=true`,
`structure_min_swing_atr=0.5`, `weight_structure_bonus=0.0`, `require_bos=false`,
`block_on_choch=false`.

---

# Task 5 — Trend-strength gate (validated; the strongest change so far)

The 1H EMA50>EMA200 cross stays the direction gate; added optional strength
sub-filters, each independently toggleable so they could be isolated via
`--compare`. Built as gates (filters), not score weights — per the Task 1 lesson.
Default off (no-op) reproduces V2.

## Sub-filter isolation (180d / 6 segments)

| Sub-filter | PF | Net | Max DD | Segs won | Keep? |
| --- | --- | --- | --- | --- | --- |
| Baseline | 1.312 | $1585 | $775 | - | - |
| price above EMA50 | 1.404 | $1900 | $660 | 4/6 | yes |
| EMA50-EMA200 gap >= 0.5% | 1.360 | $1685 | $905 | 5/6 | yes (mild) |
| EMA50 slope >= 0.2% | 1.308 | $1200 | $1465 | 3/6 | no |
| ADX rising | 1.233 | $1065 | $1075 | 3/6 | no |

price-above-EMA50 is the clear winner (better PF, net AND drawdown). Slope and
ADX-rising hurt and are dropped.

## Winning combo: price-above-EMA50 + EMA-gap >= 0.5%

| Window | Base PF | V3 PF | Base net | V3 net | Base DD | V3 DD | Segs won |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 120d | 0.985 | 1.131 | -$50 | +$340 | $735 | $545 | 3/4 |
| 180d | 1.312 | 1.515 | $1585 | $2060 | $775 | $610 | 5/6 |
| 270d | 1.154 | 1.298 | $1315 | $2010 | $910 | $885 | 6/9 |

Robust across all three windows: PF up everywhere, net up substantially (120d
flips to profit, 270d +53%), majority of segments won, and drawdown better/flat.
Caveat: max consecutive losses rose on 270d (19 -> 28) even though dollar DD
improved.

## Stacking check: Task 1 + Task 5 does NOT help

Structure significance gate ON TOP of the trend combo was slightly worse than the
trend combo alone (180d PF 1.515 -> 1.495, DD $610 -> $830; 270d PF 1.298 ->
1.238). They overlap, so stacking over-filters. Ship the trend filter alone.

## Verdict

**Task 5 (price-above-EMA50 + EMA-gap >= 0.5%) is the strongest validated edge and
supersedes the Task 1 structure gate.** Recommended live config (off by default,
paper-only until DB-wired):
`trend_filter_enabled=true`, `trend_require_price_above_ema50=true`,
`trend_min_ema_gap_pct=0.5`, slope/ADX-rising off, and structure quality OFF.
