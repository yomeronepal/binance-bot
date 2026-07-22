# Futures Opposite-Signal Exit Monitor — Design

## Summary

Monitor open **live futures** trades and, when a trade is working against us
(in drawdown) **and** the day-trade engine generates an opposite-direction
signal for that symbol at ≥0.70 confidence, **arm** the trade. Once armed,
auto-close it at market **only when it has recovered to breakeven/profit** —
never realize a loss through this path (the trade's existing stop-loss still
handles the downside). This salvages trades that are turning against us by
taking the next green exit instead of round-tripping to the stop.

## Goals

- Detect the (drawdown + opposite day-trade signal) condition on open futures
  trades.
- Arm such trades persistently.
- Auto-close an armed trade at market as soon as it is at/above a small profit
  threshold (net of fees).
- Ship default-off with a shadow (log-only) mode to validate before it acts.

## Non-Goals

- Never closes at a loss (that stays with the existing SL / cut-loser).
- No new signal generation; consumes existing `DayTradeSignal` rows.
- No change to entry logic or the day-trade engine.
- Not a general trailing-stop (that is `check_and_update_dynamic_trailing`).

## Captured requirements (user)

- Auto-close **live** futures trades.
- Close **only if at profit/breakeven** when the condition is met (never at a
  loss).
- "Opposite signal" = a **day-trade engine** signal, opposite direction,
  **confidence ≥ 0.70**.

## Existing machinery (reused)

- `FuturesTrade` (`backend/signals/models/futures.py:353`): `status` OPEN,
  `direction`, `symbol` (plain string), `entry_price`, `mark_price`,
  `unrealized_pnl`, `unrealized_pnl_percentage`, `quantity`, `entry_time`,
  `cut_loser_triggered` (`:531`), `close_trade(exit_price, status)` (`:635`).
- Monitor loop `sync_futures_trades_with_binance`
  (`backend/scanner/tasks/golden_window_trader.py:785`): every 30s, iterates
  `FuturesTrade.objects.filter(status='OPEN')`, writes live
  `mark_price`/`unrealized_pnl`/`pnl_pct`, then calls
  `check_and_execute_cut_loser(trade, pnl_pct, settings)` (`:908`). New check
  slots in right here.
- Close sequence (mirror cut-loser `:90-135`): `cancel_all_orders(symbol)` →
  `close_position(symbol, direction, quantity)` →
  `trade.close_trade(exit_price, status)`. Sync wrapper:
  `FuturesTradingService.close_trade(trade)` (`futures_trader.py:2064`).
- Opposite signal source: `DayTradeSignal`
  (`backend/signals/models/daytrade.py`) — `symbol` (plain string, matches
  `FuturesTrade.symbol`), `direction`, `confidence`, `status`, `created_at`.
- Config: `FuturesTradingSettings` (`futures.py:11`, `get_settings()`).

## Design

### Config (new fields on FuturesTradingSettings; migration + admin)

- `opposite_exit_enabled` (bool, default **False**) — master switch.
- `opposite_exit_shadow_mode` (bool, default **True**) — when True, log what it
  *would* arm/close but take no action. Lets us validate on live data first.
- `opposite_exit_min_confidence` (Decimal, default **0.70**) — opposite-signal
  confidence floor.
- `opposite_exit_min_profit_pct` (Decimal, default **0.20**) — minimum
  unrealized PnL as % of margin required to close (covers round-trip fees so
  the exit is net-positive). Tunable.

### Trade state (new fields on FuturesTrade; migration)

- `opposite_exit_armed` (bool, default False, indexed).
- `opposite_exit_armed_at` (datetime, null).
- New `status` choice `CLOSED_REVERSAL` (distinguish these exits in reporting).

### Arming (in the monitor loop)

For each OPEN trade each tick, when `opposite_exit_enabled`:
1. Compute current `pnl_pct` (already done in the loop).
2. If **not yet armed** and the trade is **in drawdown** (`pnl_pct < 0`):
   - Look for a qualifying opposite signal:
     ```python
     opp = 'SHORT' if trade.direction == 'LONG' else 'LONG'
     DayTradeSignal.objects.filter(
         symbol=trade.symbol, direction=opp, status='ACTIVE',
         confidence__gte=float(settings.opposite_exit_min_confidence),
         created_at__gt=(trade.entry_time or trade.created_at),
     ).exists()
     ```
   - If found: set `opposite_exit_armed=True`, `opposite_exit_armed_at=now`,
     save, log (and in shadow mode, log only — still persist the armed flag so
     we can measure). Optionally push-notify.

### Closing (in the monitor loop)

3. If **armed** and `pnl_pct >= opposite_exit_min_profit_pct`:
   - **Shadow mode**: log `WOULD close <symbol> reversal-exit at +X%`; do not act.
   - **Live**: `cancel_all_orders` → `close_position` →
     `trade.close_trade(mark_price, 'CLOSED_REVERSAL')`. Mirror the cut-loser
     thread/asyncio pattern (`golden_window_trader.py:90-135`).

Placed alongside `check_and_execute_cut_loser`; both use the same close path and
are guarded by `status='OPEN'`, so they cannot double-close.

### Data flow

`sync_futures_trades_with_binance` → per OPEN trade: update mark/pnl →
cut-loser check → **opposite-exit check** (arm if drawdown + opposite ≥0.70
day-trade signal; close if armed and pnl_pct ≥ min_profit_pct) → account
rollup.

## Edge cases

- **Symbol not in day-trade universe** → no opposite signal ever appears → never
  arms. Acceptable (documented limitation).
- **Never closes at a loss**: the close branch requires `pnl_pct >= min_profit`
  (> 0). Downside remains the existing SL/cut-loser.
- **Armed but never recovers** → original SL closes it; the armed flag is
  harmless.
- **Opposite signal expires** before recovery → trade stays armed (we treat the
  reversal warning as sticky once seen). Reasonable; revisit if noisy.
- **Idempotency**: once `status != 'OPEN'`, the trade is skipped.

## Validation

- **Unit tests**: arming requires drawdown + qualifying opposite signal
  (direction/confidence/recency); no-arm when in profit or signal too weak/old;
  close only fires when armed and `pnl_pct >= min_profit`; shadow mode never
  calls the close path.
- **Shadow run on live**: deploy with `opposite_exit_enabled=True` +
  `opposite_exit_shadow_mode=True` for a period; review logs of would-arm /
  would-close events against actual trade outcomes. Flip shadow off only once
  the events look correct.

## Error handling

- Signal lookup / Binance calls wrapped; any error logs a warning and skips this
  trade for the tick (never breaks the monitor loop).
- Close failures leave the trade OPEN + armed to retry next tick.

## Files touched

- `backend/signals/models/futures.py` — 4 settings fields + 2 trade fields +
  `CLOSED_REVERSAL` status.
- `backend/signals/migrations/` — migration(s).
- `backend/signals/admin.py` — expose the new settings.
- `backend/scanner/tasks/golden_window_trader.py` — arming + closing check in
  the sync loop (a `check_and_execute_opposite_exit` helper mirroring
  `check_and_execute_cut_loser`).
- tests for the arm/close logic.

## Rollout

1. PR (all default-off; shadow default-on) → merge → deploy.
2. Enable `opposite_exit_enabled=True` (shadow still on) → observe would-act
   logs on live trades.
3. Once validated, set `opposite_exit_shadow_mode=False` to let it act.

## Rollback

- `opposite_exit_enabled=False` in admin (no deploy). Armed flags become inert.
