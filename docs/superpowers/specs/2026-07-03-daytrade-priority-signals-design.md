# Day-Trade Priority Signals — Design

## Summary

Mark day-trade signals that are generated while the current time falls inside an
active `DayTradeSession` window as **priority**, and surface that flag in the
day-trade signals list, bot performance, and history. This mirrors the v1
engine's existing `is_priority` mechanism (golden-window signals). It is a
display-only marker: it does not change which signals are taken, execution, or
position sizing.

## Goals

- A `DayTradeSignal` created during an active `DayTradeSession` window is flagged
  `is_priority = True`.
- The flag is copied onto the resulting `DayTradePaperTrade` so it persists on
  the trade for bot performance and history.
- The flag is exposed by the day-trade signal, trade, and open-position APIs.
- The frontend shows a priority badge on the day-trade signal card and a
  priority indicator in bot performance and history.

## Non-Goals

- No change to signal generation logic, execution, or position sizing.
- No backfill of `is_priority` on existing signals/trades (forward-only, like v1).
- No new "priority only" filter (bot performance already has the
  `window=ai|outside` session filter).

## Definitions

- **Trading session**: an active `DayTradeSession` window
  (`backend/signals/models/daytrade.py:885`), the day-trade equivalent of v1's
  golden window. Windows are auto-discovered by the daily optimizer
  (`optimize-daytrade-sessions-daily`, `backend/config/celery.py:171`).
- **Priority**: a signal (and its trade) whose generation time, expressed in
  Nepal Time (UTC + 5h45m), falls inside an active `DayTradeSession` per
  `DayTradeSession.covers(hour, weekday)` (`daytrade.py:933`).

## Reference: the v1 pattern being mirrored

- `Signal.is_priority` field: `backend/signals/models/base.py:409`.
- Auto-set in `Signal.save()` when new: `base.py:527-532` via
  `is_high_winrate_hour()` (`base.py:505-514`), which checks
  `TradingSession.get_matching_session(nepal_now)`.
- Copied onto `PaperTrade.is_priority` (`base.py:780`) at trade open in
  `backend/signals/services/paper_trader.py:137-138`.
- Rendered as `⭐ PRIORITY` on the v1 signal card
  (`client/src/components/signals/SignalCard.jsx:74`) and as a `⚡` icon in bot
  performance open positions (`client/src/pages/BotPerformance.jsx:1063`) and the
  history table (`BotPerformance.jsx:1169`).

## Design

### Backend

**1. Model fields + migration**

- Add `is_priority = models.BooleanField(default=False, db_index=True)` to
  `DayTradeSignal` (`backend/signals/models/daytrade.py:24`).
- Add `is_priority = models.BooleanField(default=False, db_index=True)` to
  `DayTradePaperTrade` (`backend/signals/models/daytrade.py:169`).
- One migration in the `signals` app adding both fields.

**2. Session check on the session model**

- Add `DayTradeSession.is_priority_now()` (classmethod) on
  `backend/signals/models/daytrade.py`. It computes Nepal Time
  (`timezone.now()` + 5h45m), derives `hour` and `weekday()`, and returns
  `True` if any `DayTradeSession.objects.filter(is_active=True)` matches via
  `covers(hour, weekday)`. Analogous to v1 `Signal.is_high_winrate_hour()`.
- Keep it defensive: return `False` on any error or when no active session
  matches (a signal generated outside any window is simply not priority).

**3. Set the flag at signal creation**

- In `DayTradeSignal.save()`, when `self.pk` is not set, assign
  `self.is_priority = DayTradeSession.is_priority_now()` before `super().save()`.
  Setting it in `save()` (rather than only in the engine's `get_or_create`
  defaults) mirrors v1 and guarantees the flag regardless of creation path.
- The engine creation site (`backend/scanner/strategies/daytrade_signal_engine.py:671`
  `get_or_create`) needs no change; `save()` handles it.

**4. Copy the flag onto the trade**

- In `backend/scanner/tasks/daytrade_executor.py` `_open_trade_from_signal`
  (`:77-98`), add `is_priority=signal.is_priority` to the
  `DayTradePaperTrade.objects.create(...)` call. Mirrors v1's
  `paper_trader.py:137-138`.

**5. Expose via APIs**

- Add `'is_priority'` to `DayTradeSignalSerializer.fields`
  (`backend/signals/serializers/daytrade.py:19`) and
  `DayTradePaperTradeSerializer.fields` (`:47`).
- Ensure the open-positions payload (`daytrade_open_positions`,
  `backend/signals/views/daytrade.py:261`) includes `is_priority` for each
  position, so the frontend positions list can render it.

### Frontend

**6. Day-trade signal card**

- In `client/src/components/signals/DayTradeSignalCard.jsx` header row
  (`:49-58`), add a `⭐ PRIORITY` amber badge shown when `signal.is_priority`,
  styled to match the v1 `SignalCard.jsx:74` badge.

**7. Bot performance + history**

- No new code. The shared `client/src/pages/BotPerformance.jsx` already renders
  the priority `⚡` for `position.is_priority` (`:1063`) and `trade.is_priority`
  (`:1169`). Once the serializers emit the field, the day-trade source (which
  reuses this component) shows it automatically. Verify only.

## Data Flow

1. Scanner runs at 15m candle close → engine generates a signal → `save()`
   evaluates `DayTradeSession.is_priority_now()` → `is_priority` stored on the
   `DayTradeSignal`.
2. Executor opens a trade from the signal → copies `is_priority` onto the
   `DayTradePaperTrade`.
3. APIs serialize `is_priority` on signals, trades, and open positions.
4. Frontend renders the badge on the signal card and the `⚡` in bot
   performance + history.

## Edge Cases

- **No active sessions**: `is_priority_now()` returns `False`; nothing is
  marked. Expected until the optimizer has populated windows.
- **Existing rows**: remain `is_priority = False` (forward-only). Acceptable.
- **Timezone**: use the same NPT offset (UTC + 5h45m) v1 uses, for consistency
  with `DayTradeSession.covers` semantics (which already operate in NPT).

## Testing

- Unit-test `DayTradeSession.is_priority_now()`: active window covering the
  current NPT hour/weekday → `True`; no matching window → `False`; no active
  sessions → `False`.
- Unit-test that a new `DayTradeSignal.save()` sets `is_priority` from the
  session check (patched to `True`/`False`).
- Unit-test that `_open_trade_from_signal` copies `is_priority` onto the trade.
- Verify serializers include `is_priority` and the positions payload carries it.
- Frontend: verify the badge renders when `is_priority` is true on a signal
  card, and the `⚡` shows in bot performance/history for a priority trade.

## Files Touched

- `backend/signals/models/daytrade.py` (2 fields + `is_priority_now()` + `save()`).
- `backend/signals/migrations/` (new migration).
- `backend/scanner/tasks/daytrade_executor.py` (copy flag onto trade).
- `backend/signals/serializers/daytrade.py` (expose on signal + trade).
- `backend/signals/views/daytrade.py` (positions payload includes flag).
- `client/src/components/signals/DayTradeSignalCard.jsx` (priority badge).

## Rollout

- Forward-only, display-only; safe to deploy behind the normal PR → deploy flow.
- After deploy, priority marks appear on signals generated during active
  sessions and on the trades they open.
