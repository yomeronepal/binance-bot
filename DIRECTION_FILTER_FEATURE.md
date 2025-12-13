# Direction Filter Feature for Bot Performance

## Overview

Added the ability to filter bot performance metrics by trade direction (ALL, LONG, SHORT) across all public paper trading endpoints.

## Endpoints Updated

### 1. Public Summary Endpoint
**URL**: `GET /api/public/paper-trading/summary/`

**Query Parameters**:
- `direction` - Filter by trade direction: `ALL` (default), `LONG`, or `SHORT`
- `golden_window` - Filter Golden Window 1 trades
- `golden_window_2` - Filter Golden Window 2 trades
- `outside_golden_window` - Filter trades outside Golden Windows

**Examples**:
```bash
# Get all trades performance
curl "http://localhost:8000/api/public/paper-trading/summary/"

# Get LONG trades only
curl "http://localhost:8000/api/public/paper-trading/summary/?direction=LONG"

# Get SHORT trades only
curl "http://localhost:8000/api/public/paper-trading/summary/?direction=SHORT"

# Combine filters: SHORT trades in Golden Window 1
curl "http://localhost:8000/api/public/paper-trading/summary/?direction=SHORT&golden_window=true"
```

### 2. Public Performance Endpoint
**URL**: `GET /api/public/paper-trading/performance/`

**Query Parameters**:
- `direction` - Filter by trade direction: `ALL` (default), `LONG`, or `SHORT`
- `days` - Limit to last N days
- `golden_window` - Filter Golden Window 1 trades
- `golden_window_2` - Filter Golden Window 2 trades
- `outside_golden_window` - Filter trades outside Golden Windows

**Examples**:
```bash
# Get all trades performance metrics
curl "http://localhost:8000/api/public/paper-trading/performance/"

# Get LONG trades performance
curl "http://localhost:8000/api/public/paper-trading/performance/?direction=LONG"

# Get SHORT trades performance for last 7 days
curl "http://localhost:8000/api/public/paper-trading/performance/?direction=SHORT&days=7"
```

### 3. Public Paper Trades List
**URL**: `GET /api/public/paper-trading/`

**Query Parameters**:
- `direction` - Filter by trade direction: `LONG` or `SHORT`
- `status` - Filter by status
- `market_type` - Filter by market type
- `symbol` - Filter by symbol
- `golden_window` - Filter Golden Window 1 trades
- `golden_window_2` - Filter Golden Window 2 trades
- `outside_golden_window` - Filter trades outside Golden Windows

**Examples**:
```bash
# Get LONG trades list
curl "http://localhost:8000/api/public/paper-trading/?direction=LONG"

# Get closed SHORT trades
curl "http://localhost:8000/api/public/paper-trading/?direction=SHORT&status=CLOSED_WIN"
```

## Test Results

Based on current bot data:

### ALL Trades (No Filter)
```json
{
  "total_trades": 862,
  "win_rate": 53.55%,
  "total_profit_loss": $21,169.27,
  "avg_profit_loss": $25.08,
  "profitable_trades": 452,
  "losing_trades": 391
}
```

### LONG Trades Only
```json
{
  "total_trades": 194,
  "win_rate": 38.42%,
  "total_profit_loss": -$1,064.31,
  "avg_profit_loss": -$5.60,
  "profitable_trades": 73,
  "losing_trades": 116
}
```

### SHORT Trades Only
```json
{
  "total_trades": 668,
  "win_rate": 57.95%,
  "total_profit_loss": $22,233.58,
  "avg_profit_loss": $33.99,
  "profitable_trades": 379,
  "losing_trades": 275
}
```

## Key Insights

From the test data:
1. **SHORT trades are significantly more profitable**: 57.95% win rate vs 38.42% for LONG
2. **SHORT trades have higher average profit**: $33.99 vs -$5.60 for LONG
3. **MORE SHORT signals generated**: 668 SHORT vs 194 LONG trades
4. **LONG trades are currently unprofitable**: -$1,064.31 total P/L

This suggests the strategy may benefit from:
- Focusing on SHORT signals
- Improving LONG signal filters
- Analyzing why LONG trades underperform

## Frontend Integration

Update your frontend components to add direction filter dropdown:

```javascript
// Example React component
const [direction, setDirection] = useState('ALL');

// Fetch with direction filter
const fetchPerformance = async () => {
  const response = await fetch(
    `/api/public/paper-trading/summary/?direction=${direction}`
  );
  const data = await response.json();
  // Update UI
};

// Dropdown UI
<select value={direction} onChange={(e) => setDirection(e.target.value)}>
  <option value="ALL">All Trades</option>
  <option value="LONG">LONG Only</option>
  <option value="SHORT">SHORT Only</option>
</select>
```

## API Response Example

**Request**: `GET /api/public/paper-trading/summary/?direction=SHORT`

**Response**:
```json
{
  "performance": {
    "total_trades": 668,
    "open_trades": 13,
    "win_rate": 57.95107033639144,
    "total_profit_loss": 22233.58410899,
    "avg_profit_loss": 33.99630597704893,
    "best_trade": 22233.58410899,
    "worst_trade": 22233.58410899,
    "avg_duration_hours": 184.13,
    "max_drawdown": 3108.6045862,
    "profitable_trades": 379,
    "losing_trades": 275,
    "unrealized_pnl": -10.41194072,
    "total_pnl": 22223.17216827
  },
  "open_trades_count": 13,
  "recent_closed_trades": [...],
  "bot_total_pnl": 22233.58410899,
  "bot_win_rate": 57.95107033639144,
  "bot_total_trades": 668,
  "bot_realized_pnl": 22233.58410899,
  "bot_unrealized_pnl": -10.41194072
}
```

## Files Modified

1. **backend/signals/views_public_paper_trading.py**
   - Updated `public_summary()` - Added direction filter (lines 450-456)
   - Updated `public_performance()` - Added direction filter (lines 115-121)
   - `public_paper_trades_list()` - Already had direction filter

## Testing Commands

```bash
# Test ALL trades
curl -s "http://localhost:8000/api/public/paper-trading/summary/" | python -m json.tool

# Test LONG trades
curl -s "http://localhost:8000/api/public/paper-trading/summary/?direction=LONG" | python -m json.tool

# Test SHORT trades
curl -s "http://localhost:8000/api/public/paper-trading/summary/?direction=SHORT" | python -m json.tool

# Test with multiple filters
curl -s "http://localhost:8000/api/public/paper-trading/summary/?direction=SHORT&golden_window=true" | python -m json.tool
```

## Performance Comparison Table

| Direction | Total Trades | Win Rate | Total P/L | Avg P/L per Trade | Status |
|-----------|-------------|----------|-----------|-------------------|---------|
| **ALL** | 862 | 53.55% | $21,169.27 | $25.08 | ✅ Profitable |
| **LONG** | 194 | 38.42% | -$1,064.31 | -$5.60 | ❌ Losing |
| **SHORT** | 668 | 57.95% | $22,233.58 | $33.99 | ✅ Very Profitable |

## Recommendations Based on Data

1. **Strategy Adjustment**: Consider focusing primarily on SHORT signals
2. **LONG Signal Improvement**: Investigate why LONG trades have only 38% win rate
3. **Position Sizing**: Consider larger position sizes for SHORT trades
4. **Risk Management**: Review LONG trade entry/exit criteria

## Conclusion

The direction filter feature provides valuable insights into trade performance by direction. Current data shows SHORT trades significantly outperform LONG trades, suggesting potential strategy optimizations.
