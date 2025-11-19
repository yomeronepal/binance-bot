# Django Admin Export Guide

## Quick Start - Export Paper Trading Data from Admin Panel

Your Django admin now has **2 export actions** for paper trading data analysis.

## Accessing the Admin Panel

1. **Open your browser** and navigate to:
   ```
   http://your-server-url/admin/
   ```

2. **Login** with your admin credentials

3. **Navigate to:** `Signals > Paper trades`

## Export Options

### Option 1: Export ALL Paper Trades (Complete Analysis)

**Use case:** Get complete analysis of all paper trades in your database

**Steps:**
1. Go to Paper Trades list in admin
2. Click the checkbox at the top to select all (or don't select any)
3. From the **Action dropdown**, select: `📥 Export ALL paper trades to JSON (complete analysis)`
4. Click **Go**
5. A JSON file will download automatically with timestamp

**Filename format:** `paper_trades_complete_export_YYYYMMDD_HHMMSS.json`

### Option 2: Export SELECTED Trades Only

**Use case:** Export specific trades based on filters or manual selection

**Steps:**
1. Go to Paper Trades list in admin
2. **Optional:** Use filters on the right sidebar:
   - Filter by Status (OPEN, CLOSED_TP, CLOSED_SL, etc.)
   - Filter by Direction (LONG, SHORT)
   - Filter by Market Type (SPOT, FUTURES)
   - Filter by Exit Time (date range)
   - Search by Symbol or Username
3. **Select trades** by clicking checkboxes next to specific trades
4. From the **Action dropdown**, select: `📥 Export SELECTED trades to JSON`
5. Click **Go**
6. A JSON file will download with only selected trades

**Filename format:** `paper_trades_selected_export_YYYYMMDD_HHMMSS.json`

## Using Filters for Targeted Analysis

### Example 1: Export Last Week's Trades
1. Filter by "Exit time" → Select date range (last 7 days)
2. Use "Export ALL" action
3. Get complete analysis of just last week

### Example 2: Export Only Winning Trades
1. Unfortunately Django admin doesn't have P/L filter by default
2. Use "Export ALL" then filter JSON manually
3. Or export all and use the `performance_by_period` section

### Example 3: Export Specific Symbol
1. Use search bar → Enter "BTCUSDT"
2. Select all filtered results
3. Use "Export SELECTED" action

### Example 4: Export Only Stop Loss Hits
1. Filter by Status → Select "Closed - Stop Loss Hit"
2. Use "Export ALL" action
3. Analyze why SL is being hit

## What's Included in the Export

The exported JSON file contains comprehensive analysis:

✅ **Export Information**
- Generation timestamp
- Who exported it
- Total trades count

✅ **Summary Statistics**
- Win rate, profit factor, Sharpe ratio
- Average win/loss, max drawdown
- Consecutive win/loss streaks

✅ **Individual Trade Details**
- Entry/exit prices, P/L, duration
- Signal information (timeframe, confidence)
- All timestamps and metadata

✅ **Analysis by Symbol**
- Performance breakdown per trading pair
- Win rates and total P/L per symbol

✅ **Analysis by Direction**
- LONG vs SHORT performance comparison

✅ **Analysis by Timeframe**
- Which timeframes perform best

✅ **Analysis by Exit Type**
- TP vs SL hit rates
- Average profit/loss per exit type

✅ **Time Period Analysis**
- Last 7 days, 30 days, 90 days, all-time
- Performance trends over time

✅ **Account Information**
- Balance, equity, ROI
- Trading settings and limits

## Success Message

After export, you'll see a green success message at the top:

```
Successfully exported X closed trades and Y open trades.
Win Rate: Z%, Total P/L: $W
```

This gives you instant insight into your current performance!

## Tips for Best Results

### 1. Export Regularly
- Export weekly to track performance trends
- Compare exports to see improvement

### 2. Use Filters Strategically
- Export problematic periods separately
- Analyze losing trades independently
- Focus on specific symbols or timeframes

### 3. Compare Exports
- Export "last 30 days" periodically
- Track if strategy improvements are working
- Identify when performance changed

### 4. Analyze Locally
Once downloaded, use Python or any JSON viewer to analyze:

```python
import json

with open('paper_trades_complete_export_20251119_120000.json', 'r') as f:
    data = json.load(f)

print("Win Rate:", data['summary_statistics']['win_rate'])
print("Best Symbol:", max(
    data['analysis_by_symbol'].items(),
    key=lambda x: x[1]['win_rate']
))
```

## Troubleshooting

### Issue: No data exported
**Solution:** Make sure you have paper trades in the database. Check that trades are closed (not just pending).

### Issue: Download doesn't start
**Solution:** Check browser pop-up blocker. Make sure you're logged into admin with proper permissions.

### Issue: Want to export open trades only
**Solution:** Filter by Status → Select "Open" or "Pending Entry", then export selected.

### Issue: File is too large
**Solution:** Use filters to narrow down the date range, then export selected trades instead of all.

## Next Steps

1. **Export your current data**
2. **Share the JSON file** for detailed analysis and optimization recommendations
3. **Implement improvements** based on insights
4. **Re-export and compare** to validate changes

## Advanced Usage

### Export for Specific User
If you have multiple users:
1. Search for username in search bar
2. Select all results
3. Export selected

### Export Date Ranges
1. Filter by "Exit time"
2. Select date range
3. Export all filtered results

### Periodic Monitoring
Set up a routine:
- Weekly export on Mondays
- Compare week-over-week
- Track win rate trends
- Identify when to adjust strategy

---

## Quick Command Summary

| What to Export | How |
|----------------|-----|
| Everything | Action → Export ALL |
| Last week | Filter exit_time → Export ALL |
| Specific symbol | Search symbol → Export SELECTED |
| Only losses | Filter CLOSED_SL → Export ALL |
| Specific user | Search username → Export SELECTED |
| Custom selection | Check boxes → Export SELECTED |

---

**Need Help?**

If you need assistance analyzing the exported data or want specific optimization recommendations, share your exported JSON file for detailed analysis!
