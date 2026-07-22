# Cost-Aware Day-Trade Paper Executor — Design

## Summary

The day-trade paper executor records **gross** P/L — no fees, slippage, or
funding. This made the engine look profitable (+$914 gross / +$1,423 in 30d)
while the *same engine live* lost money (−$47). Analysis showed the gross edge
is ~0.073% of notional per trade — **below the 0.08% taker fee alone** — so net
of real costs the edge is negative (−$94 fees-only, −$1,102 with light
slippage). This change makes paper P/L reflect real trading costs so every
future decision is measured against the truth.

## Goals

- Deduct realistic round-trip costs (fees + slippage + funding) from each closed
  day-trade paper trade's P/L.
- Store the deducted cost transparently (`fees_paid`).
- Expose it via the API.
- Provide an idempotent backfill so historical trades show net P/L too.

## Non-Goals

- No change to signal generation, entry, or exit *levels* (verified: paper
  already exits at TP1/SL single-leg — the exit logic is not the problem).
- No change to the live futures path (separate work).

## Cost model (mirrors the backtest engine, PR #75)

- `taker_fee_rate = 0.0004`, `slippage_rate = 0.0002`, `funding_rate_8h = 0.0001`
  — overridable via Django settings (`DAYTRADE_TAKER_FEE_RATE`, etc.).
- `entry_notional = quantity × entry_price`; `exit_notional = quantity × exit_price`;
  `turnover = entry_notional + exit_notional`.
- `cost = turnover × (taker + slippage) + entry_notional × funding_8h × (hours // 8)`.

## Design

- **Model**: add `DayTradePaperTrade.fees_paid` (Decimal, default 0); reword
  `profit_loss` help text to "net of fees". Migration `0064`.
- **Executor** (`daytrade_executor.py`): add `_cost_rates()` + `_trade_cost()`;
  `_finalize` sets `fees_paid = cost` and `profit_loss = realized_pnl − cost`
  (and recomputes `profit_loss_percentage`).
- **Serializer**: add `fees_paid` to `DayTradePaperTradeSerializer`.
- **Backfill command** `backfill_daytrade_fees` (dry-run by default, `--apply`
  to persist): for closed trades with `fees_paid == 0`, compute the cost, set
  `fees_paid`, re-net `profit_loss`, and recompute account metrics. Idempotent.

## Data flow

Trade closes → `_close_remaining` → `_finalize` computes cost, stores
`fees_paid`, sets `profit_loss = realized_pnl − cost` → account rollup uses the
net number → dashboard shows net P/L.

## Testing

- Unit tests for `_trade_cost` (fee+slippage, funding after 8h, none before,
  scaling with exit price). — 4 tests.
- End-to-end `_finalize` check: realized 5, cost 1.206 → net 3.794.
- Backfill dry-run runs and reports gross/costs/net.

## Rollout

1. Merge + deploy (migration applies; new closes are net automatically).
2. Run `backfill_daytrade_fees --apply` once to net historical trades so the
   dashboard reflects reality.
3. Iterate the strategy on honest (net) numbers toward a real net-positive edge.

## Forward pointer

Once paper is honest, the "earner" work is raising edge-per-trade above the
~0.16% cost hurdle: fewer/higher-confidence trades, letting winners run past
TP1, and maker/limit entries (cut taker fees ~4×). Only fund live once
cost-aware paper is net-positive.
