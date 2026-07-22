# Futures Signal-Quality Gate — Design

## Summary

The live futures bot loses real money (170 closed trades, 39.4% win, −$46 PnL,
profit factor 0.81, −$24 in the last 30 days). The confirmed root cause is
universe quality: it traded **125 distinct symbols across 170 trades** — ~1.4
trades per symbol, including illiquid junk (`USELESSUSDT`, `AIAUSDT`,
`LYNUSDT`). It has **no universe screening**, unlike the profitable day-trade
engine. Cross-engine, LONGs are net-negative (v1 LONG −$9,013 vs SHORT
+$10,184; day-trade LONG −$169 vs SHORT +$1,105); SHORTs carry the edge.

This feature stops the bleed in two parts: (1) flip existing config knobs that
are already enforced, and (2) add the missing universe screen to the futures
entry path.

## Goals

- Stop the live futures bot from trading illiquid/junk symbols.
- Stop taking LONG futures trades (SHORT-only) via the existing flag.
- Raise the confidence floor for futures entries.
- Ship the new screening code default-off, validated by a dry-run before enabling.

## Non-Goals

- No change to the day-trade engine (it is profitable; leave it alone).
- No new trend-gate for longs (deferred; SHORT-only is the immediate move).
- No change to how signals are generated — only which ones get executed.
- The opposite-signal exit monitor is a separate feature (separate spec).

## Data (prod, at design time)

- Futures: 170 closed, 39.4% win, −$46.21 total, PF 0.81, −$23.73 (30d),
  125 distinct symbols, avg notional ~$123/trade, est. round-trip taker fees
  ~$16.78. 169/170 trades have a nulled `signal` FK (confidence not
  measurable from history; entry-time gate still applies).
- Worst futures symbols: `SUIUSDT`, `AIAUSDT`, `USELESSUSDT`, `RPLUSDT`,
  `CRVUSDT`, `LYNUSDT`.

## Existing machinery (reused)

- `FuturesTradingSettings` (`backend/signals/models/futures.py:11`, singleton
  via `get_settings()`): `trade_long` (`:88`), `trade_short` (`:93`),
  `min_signal_confidence` (`:74`), `can_trade()` (`:319`, enforces all three).
- `get_prioritized_signals(settings, limit)`
  (`backend/scanner/tasks/golden_window_trader.py:337`) already honors
  `trade_long`/`trade_short` (`:377-380`) and feeds
  `golden_window_auto_trader` (`:668`).
- Day-trade screen to mirror: `_screen_universe` / `_screen_thresholds` /
  `_range_pct` in `backend/scanner/tasks/daytrade_scanner.py:39-109`;
  blacklist via `BlacklistedSymbol.get_blacklisted_symbols()`.

## Design

### Part 1 — Config flips (no code; applied on prod)

On `FuturesTradingSettings.get_settings()`:
- `trade_long = False` — SHORT-only. Already enforced at `can_trade:334` and
  `get_prioritized_signals:377`.
- `min_signal_confidence = 0.75` — already enforced at `can_trade:340`.

These take effect immediately (read fresh each 30s tick) and are reversible in
the admin. No deploy required.

### Part 2 — Universe screening (new code, default-off)

**Flag.** Add `futures_universe_screen_enabled = BooleanField(default=False)`
to `FuturesTradingSettings` (+ migration + admin fieldset entry). When False,
behavior is unchanged.

**Thresholds.** Read from Django settings with day-trade-matching defaults so
they can be tuned without a deploy:
- `FUTURES_MIN_QUOTE_VOLUME_USDT` = 10_000_000
- `FUTURES_MIN_24H_RANGE_PCT` = 2.0
- `FUTURES_MAX_24H_RANGE_PCT` = 40.0

**Screening helper.** `screen_futures_symbols(symbols) -> set[str]` in a small
module (e.g. `backend/scanner/services/futures_universe.py`):
1. Fetch `/fapi/v1/ticker/24hr` once via `BinanceFuturesClient`, cached ~60s
   under a Redis key using best-effort cache access (never raise on cache
   failure).
2. Keep symbols with `quoteVolume >= floor` and `2.0 <= 24h_range% <= 40.0`.
3. Drop blacklisted symbols.
4. Return the passing set.
Reuses the `_range_pct` logic (extract to shared util or duplicate the small
function to avoid a cross-module import cycle).

**Hook point.** In `get_prioritized_signals` (`golden_window_trader.py:337`),
when `settings.futures_universe_screen_enabled` is True, filter the candidate
signals to those whose `symbol` is in `screen_futures_symbols(candidate_symbols)`
before returning. When False, return the current list unchanged.

**Fail-open.** If the ticker fetch errors, log a warning and skip screening for
that tick (return candidates unfiltered) — never halt trading on a transient
Binance/API blip. Matches the day-trade screen's tolerant behavior.

### Data flow

`golden_window_auto_trader` → `get_prioritized_signals(settings, limit)` →
*(flag on)* `screen_futures_symbols(symbols)` → drop signals on
junk/illiquid/blacklisted symbols → `execute_futures_trade` on survivors only.

## Validation

- **Unit tests** for `screen_futures_symbols`: passes a liquid in-band symbol;
  drops a low-volume symbol; drops an out-of-band (too flat / too volatile)
  symbol; drops a blacklisted symbol; fail-open returns input on fetch error.
- **Dry-run report** (management command or shell snippet): run the screen
  against the distinct symbols traded by futures in the last 30 days and list
  which would be dropped (expect `USELESSUSDT`, `AIAUSDT`, etc.). Review this
  before flipping `futures_universe_screen_enabled = True`.

## Error handling

- Cache access is best-effort (get/set wrapped; failure treated as miss).
- Ticker-fetch failure → fail-open + warning log.
- Screening never raises into the trading loop.

## Files touched

- `backend/signals/models/futures.py` — add `futures_universe_screen_enabled`.
- `backend/signals/migrations/` — new migration.
- `backend/signals/admin.py` — expose the flag.
- `backend/scanner/services/futures_universe.py` — new screening helper.
- `backend/scanner/tasks/golden_window_trader.py` — filter in
  `get_prioritized_signals`.
- `backend/config/settings.py` — threshold defaults (optional; getattr defaults
  cover it).
- tests for the screening helper.

## Rollout

1. **Now**: apply Part 1 config flips on prod (`trade_long=False`,
   `min_signal_confidence=0.75`). Immediate bleed reduction; reversible.
2. **PR**: Part 2 screening code (default-off) → merge → deploy.
3. Run the dry-run report; if it drops the expected junk, set
   `futures_universe_screen_enabled = True` in the admin.

## Rollback

- Part 1: flip the flags back in the admin.
- Part 2: set `futures_universe_screen_enabled = False` (no deploy needed).
