# 4h Swing Engine (Paper-First Validation Harness) — Design

## Summary

Backtesting found the first strategy that clears costs out-of-sample: a **4h
breakout, gated by the 1D trend + ADX**, exiting at ATR-based ~2:1. Across 3
years net-of-cost it was +$1,458 (PF 1.07), 4/6 half-year segments positive —
real but thin and regime-dependent. Rather than tune further (overfit risk),
we run it **forward in cost-aware paper** to validate on unbiased out-of-sample
time before any money. This is a lightweight harness: persist paper trades,
monitor exits, summarize P&L. No dashboard/API yet.

## Goals

- Evaluate the validated 4h-swing rule live, once per 4h candle close.
- Open cost-aware paper trades with ATR SL/TP; monitor and close on SL/TP.
- Accumulate honest (net-of-fees) forward P&L, viewable via a summary command.
- Everything flag-gated (default off) and admin-tunable.

## Non-Goals

- No live/real orders (paper only).
- No new dashboard, API, or serializers (add later only if it proves out).
- No parameter tuning / chop filter (avoid overfitting; validate the rule as-is).
- No change to the day-trade or futures engines.

## Validated rule (locked as defaults)

- Entry timeframe 4h, trend timeframe 1D.
- Trend: 1D EMA50 vs EMA200 with ADX(1D) ≥ 20 → UP/DOWN bias.
- Entry: 4h close breaks the prior 20-bar high (long, in UP) / low (short, in DOWN).
- SL = 1.5×ATR(4h); TP = 3.0×ATR(4h) (2:1). Fixed TP (beat trailing in tests).
- One open position per symbol. Costs: fee 0.0004 + slippage 0.0002 on turnover.

## Components

### Models (`backend/signals/models/swing.py`; migration 0065)

- **`SwingStrategyConfig`** (singleton, `get_active()`): `enabled` (bool,
  default False), `symbols` (JSON, default 8 majors: BTC, ETH, BNB, XRP, LTC,
  ADA, DOGE, SOL), `entry_timeframe` ('4h'), `trend_timeframe` ('1d'),
  `adx_min` (20), `breakout_lookback` (20), `sl_atr_mult` (1.5),
  `tp_atr_mult` (3.0), `margin_per_trade` (100), `leverage` (10),
  `fee_rate` (0.0004), `slippage_rate` (0.0002).
- **`SwingPaperTrade`**: symbol, direction, entry_price, stop_loss,
  take_profit, atr_at_entry, quantity, position_size, leverage, entry_time,
  exit_price, exit_time, status (OPEN / CLOSED_TP / CLOSED_SL), profit_loss
  (net), fees_paid, profit_loss_percentage, created_at. Indexed on
  (symbol, status) and (-created_at).

### Shared rule (`backend/scanner/strategies/swing_engine.py`)

- `evaluate_swing(df_entry, df_trend, config) -> dict | None`: the single
  source of truth for the entry rule (trend from the last *closed* 1D candle,
  20-bar breakout on the last *closed* 4h candle, ATR SL/TP). Returns
  `{direction, entry, stop_loss, take_profit, atr}` or None. Look-ahead-safe:
  operates on closed candles only.

### Tasks (`backend/scanner/tasks/swing_scanner.py`)

- **`scan_swing`** — beat `crontab(minute=2, hour='0,4,8,12,16,20')` (just
  after each 4h UTC close). Loads config; if `enabled`, fetches 4h + 1D per
  symbol, drops the forming candle, calls `evaluate_swing`; if a signal fires
  and no OPEN trade exists for that symbol, opens a `SwingPaperTrade` sized
  `margin × leverage`.
- **`monitor_swing_positions`** — beat every 5 min. For each OPEN trade, fetch
  the current mark price; if it has crossed SL or TP, close at that level, net
  of round-trip cost (fee+slippage on turnover), set status + `fees_paid` +
  net `profit_loss`.
- Routed to the existing **`daytrade` queue** (low volume, 4h cadence) — no new
  worker container. Redis lock guards `scan_swing` against overlap.

### Ops

- **Admin**: register `SwingStrategyConfig` + `SwingPaperTrade` (read-only-ish).
- **`swing_summary` command**: overall + per-symbol net P&L, win%, PF, expectancy,
  and current open positions.

## Data flow

`scan_swing` (4h close) → `evaluate_swing` on closed candles → open
`SwingPaperTrade` → `monitor_swing_positions` (5 min) closes on SL/TP net of
cost → `swing_summary` reports forward P&L.

## Validation / testing

- Unit tests for `evaluate_swing`: fires long on a breakout in a 1D uptrend;
  no signal when trend is flat/opposite or no breakout; correct ATR SL/TP.
- Unit test the net-cost close math (matches the backtest cost model).
- Manual: enable config, confirm `scan_swing` logs candidates at 4h closes and
  `swing_summary` reflects trades.

## Rollout

1. Merge + deploy (models migrate; tasks idle while `enabled=False`).
2. Flip `SwingStrategyConfig.enabled = True` in admin to start forward paper.
3. Observe `swing_summary` for several weeks across whatever regime occurs.
4. Only if forward paper is net-positive → design live execution (separate spec).

## Rollback

- `enabled = False` in admin (tasks no-op). No live money ever involved.
