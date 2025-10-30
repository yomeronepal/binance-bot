# Django Management Commands Reference

This document provides comprehensive documentation for all custom Django management commands available in the trading bot application.

## Table of Contents

1. [analyze_trades](#analyze_trades) - Analyze paper trades with TP/SL diagnostics
2. [analyze_performance](#analyze_performance) - Comprehensive performance analysis with recommendations
3. [clean_database](#clean_database) - Clean all database records
4. [create_paper_account](#create_paper_account) - Create/update paper trading account
5. [monitor_backtests](#monitor_backtests) - Monitor backtest progress and generate reports

---

## analyze_trades

**Purpose:** Analyze paper trades and provide trading parameter recommendations with TP/SL distance analysis.

**File:** `backend/signals/management/commands/analyze_trades.py`

### Usage

```bash
# Basic usage - analyze open trades
docker-compose exec backend python manage.py analyze_trades

# Analyze closed trades
docker-compose exec backend python manage.py analyze_trades --status CLOSED

# Analyze specific symbol
docker-compose exec backend python manage.py analyze_trades --symbol BTCUSDT --status ALL

# Analyze trades from last 7 days
docker-compose exec backend python manage.py analyze_trades --days 7 --limit 20
```

### Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--status` | string | `OPEN` | Trade status: `OPEN`, `CLOSED`, `CANCELLED`, or `ALL` |
| `--limit` | integer | `10` | Number of sample trades to display |
| `--days` | integer | None | Analyze trades from last N days |
| `--symbol` | string | None | Filter by specific trading symbol |

### Features

- **Trade Statistics** - Counts by status (open/closed/cancelled)
- **Sample Trades Table** - Visual table with TP/SL percentages and R/R ratios
- **TP/SL Distance Analysis** - Automatic diagnosis of problematic settings
- **Performance Metrics** - Win rate, profit factor, P&L for closed trades
- **Current Parameters** - Displays active SignalConfig values
- **Actionable Recommendations** - Context-aware next steps

### Output Example

```
================================================================================
                          PAPER TRADE ANALYSIS
================================================================================

📊 OVERALL STATISTICS
  Total trades analyzed: 156
  • Open: 142
  • Closed: 12
  • Cancelled: 2

📋 SAMPLE TRADES (showing 10 of 156)
Symbol       Dir    Entry           TP           SL      TP%      SL%    R/R
--------------------------------------------------------------------------------
BTCUSDT      LONG    $43250.00  $45100.00  $42000.00    4.28%    2.89%  1.48

📏 TP/SL DISTANCE ANALYSIS
LONG Trades (95 total):
  Average TP distance: 5.80%
  Average SL distance: 4.20%
  Risk/Reward Ratio: 1:1.38

  🔍 DIAGNOSIS for LONG:
    ⚠️  PROBLEM: TP targets are TOO FAR (5.8%)
       Recommendation: Reduce tp_atr_multiplier to 1.5-2.5
```

### Related Documentation

- [ANALYZE_TRADES_COMMAND.md](ANALYZE_TRADES_COMMAND.md) - Detailed guide
- [scanner/strategies/signal_engine.py](../backend/scanner/strategies/signal_engine.py) - Parameters to adjust

---

## analyze_performance

**Purpose:** Comprehensive analysis of paper trading performance and signal generation with detailed recommendations.

**File:** `backend/signals/management/commands/analyze_performance.py`

### Usage

```bash
# Run full performance analysis
docker-compose exec backend python manage.py analyze_performance
```

### Features

1. **Paper Trading Performance Analysis**
   - Trade statistics (total, closed, open, winning, losing, breakeven)
   - Performance metrics (win rate, avg win/loss, max win/loss, total P&L)
   - Profit factor, risk/reward ratio, expectancy
   - Analysis by direction (LONG vs SHORT)
   - Top 5 symbols by trade count
   - Last 20 closed trades

2. **Signal Generation Analysis**
   - Total signal counts (bullish/bearish)
   - Top 10 symbols by signal count
   - Last 10 signals with details
   - Signal distribution analysis

3. **Signal Engine Configuration**
   - Displays current trading parameters
   - RSI ranges, ADX thresholds
   - SL/TP multipliers, confidence levels
   - Volume multipliers

4. **Improvement Recommendations**
   - Win rate assessment and solutions
   - Risk/reward ratio analysis
   - Directional bias detection
   - Step-by-step action plan
   - ML tuning recommendations

### Output Sections

```
==============================================================
PAPER TRADING PERFORMANCE ANALYSIS
==============================================================

TRADE STATISTICS:
  Total Trades:      245
  Closed Trades:     125
  Open Trades:       120
  Winning Trades:    68 (54.4%)
  Losing Trades:     57 (45.6%)
  Breakeven Trades:  0

PERFORMANCE METRICS:
  Win Rate:          54.40%
  Average Win:       $45.23
  Average Loss:      $-28.67
  Profit Factor:     2.12
  Risk/Reward Ratio: 1:1.58
  Expectancy:        $11.43 per trade

BY DIRECTION:
  LONG Trades:  78 trades, 56.4% win rate, $1234.56 PnL
  SHORT Trades: 47 trades, 51.1% win rate, $789.12 PnL

TOP 5 SYMBOLS BY TRADE COUNT:
  BTCUSDT   :  35 trades, 60.0% win rate, $ 1245.67 PnL
  ETHUSDT   :  28 trades, 53.6% win rate, $  892.34 PnL
  ...

==============================================================
SIGNAL GENERATION ANALYSIS
==============================================================

SIGNAL STATISTICS:
  Total Signals:     1234
  Bullish (LONG):    678 (54.9%)
  Bearish (SHORT):   556 (45.1%)

==============================================================
RECOMMENDED ACTION PLAN
==============================================================

STEP 1: Use ML-Based Tuning (Recommended)
  Run ML tuning to automatically find optimal parameters:
  $ docker-compose exec backend python manage.py run_mltuning
```

### When to Use

- After collecting 30+ closed trades
- Before running optimization
- To diagnose performance issues
- To understand signal generation patterns

---

## clean_database

**Purpose:** Clean all data from database for fresh start or testing. Provides both interactive and simple modes.

**File:** `backend/signals/management/commands/clean_database.py`

### Usage

```bash
# Interactive cleanup (prompts for confirmation)
docker-compose exec backend python manage.py clean_database

# Auto-confirm cleanup
docker-compose exec backend python manage.py clean_database --yes

# Keep paper accounts
docker-compose exec backend python manage.py clean_database --yes --keep-accounts

# Simple cleanup (no prompts, keeps accounts)
docker-compose exec backend python manage.py clean_database --simple
```

### Arguments

| Argument | Description |
|----------|-------------|
| `--yes` | Skip confirmation prompt and proceed with cleanup |
| `--keep-accounts` | Keep PaperAccount records (users' accounts) |
| `--simple` | Use simple cleanup mode (no prompts, keeps accounts) |

### What Gets Deleted

1. **Paper Trading** (optional: keep accounts)
   - PaperTrade (all trades)
   - PaperAccount (user accounts) - OPTIONAL

2. **Signals**
   - Signal (all generated signals)

3. **Backtesting**
   - BacktestJob, BacktestResult, BacktestTrade, BacktestMetrics

4. **Walk-Forward Analysis**
   - WalkForwardJob, WalkForwardWindow, WalkForwardSummary

5. **Monte Carlo Simulations**
   - MonteCarloSimulation, MonteCarloRun, MonteCarloDistribution

6. **ML Tuning**
   - MLTuningJob, MLTuningSample, MLPrediction, MLModel

### Interactive Mode Flow

```
================================================================================
DATABASE CLEANUP - WARNING
================================================================================

This will DELETE ALL data from the following tables:
  1. Paper Trading:
     - PaperTrade (trades)
     - PaperAccount (accounts) - OPTIONAL
  ...

Current record counts:
  PaperTrade               :    245 records
  Signal                   :   1234 records
  ...

Are you sure you want to DELETE ALL this data? (type 'YES' to confirm): YES

[1/6] Cleaning Paper Trading data...
  Keep PaperAccount records? (Y/n): y
  ✓ Deleted 245 PaperTrade records
  ✓ Kept PaperAccount records

[2/6] Cleaning Signals...
  ✓ Deleted 1234 Signal records

...

✅ Database cleanup completed successfully!

Next steps:
  1. Restart services: docker-compose restart backend celery-worker
  2. New signals will be generated with corrected RSI configuration
  3. Wait for 50-100 trades to close
  4. Run ML tuning: python manage.py run_mltuning
```

### Safety Features

- Requires explicit `'YES'` confirmation (case-sensitive)
- Shows record counts before deletion
- Uses database transactions (all-or-nothing)
- Optional preservation of PaperAccount records
- Verification step after cleanup
- Clear next steps guidance

### Use Cases

- Fresh start after parameter changes
- Clean test data
- Reset before production deployment
- Clear bad trades after bug fixes

---

## create_paper_account

**Purpose:** Create or update PaperAccount for auto-trading testing with customizable settings.

**File:** `backend/signals/management/commands/create_paper_account.py`

### Usage

```bash
# Create default account (1000 balance, first user)
docker-compose exec backend python manage.py create_paper_account

# Create account with custom balance
docker-compose exec backend python manage.py create_paper_account --balance 5000

# Create for specific user
docker-compose exec backend python manage.py create_paper_account --user john

# Custom configuration
docker-compose exec backend python manage.py create_paper_account \
  --balance 10000 \
  --max-trades 10 \
  --min-confidence 0.75 \
  --max-position-size 15.0

# Create with auto-trading disabled
docker-compose exec backend python manage.py create_paper_account --disable-auto-trading
```

### Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--balance` | float | 1000.0 | Initial balance for paper account |
| `--user` | string | first user | Username for the paper account |
| `--max-trades` | integer | 5 | Maximum number of open trades |
| `--min-confidence` | float | 0.70 | Minimum signal confidence (0-1) |
| `--max-position-size` | float | 10.0 | Maximum position size percentage |
| `--disable-auto-trading` | flag | False | Disable auto-trading (default: enabled) |

### Output Example

```
✅ PaperAccount created for user admin

Account Details:
  User:              admin
  Balance:           $1000
  Auto-trading:      ENABLED
  Min confidence:    0.7
  Max position size: 10.0%
  Max open trades:   5

Auto-trading is ENABLED - Signals will be automatically traded
```

### Account Settings Explained

- **Initial Balance**: Starting capital for paper trading
- **Min Confidence**: Only trade signals above this confidence level (0.70 = 70%)
- **Max Position Size**: Maximum percentage of balance per trade
- **Max Open Trades**: Maximum simultaneous open positions
- **Auto-trading**: Whether to automatically execute signals

### When to Use

- Initial setup before starting paper trading
- Adjusting risk parameters mid-session
- Testing different confidence levels
- Changing maximum position size

### Integration with Auto-Trading

When auto-trading is enabled:
1. New signals above `min_confidence` are automatically traded
2. Position size is calculated from `max_position_size`
3. New trades only open if below `max_open_trades`
4. Respects balance availability

---

## monitor_backtests

**Purpose:** Monitor backtest progress in real-time and generate comprehensive reports grouped by volatility.

**File:** `backend/signals/management/commands/monitor_backtests.py`

### Usage

```bash
# Monitor specific backtest IDs
docker-compose exec backend python manage.py monitor_backtests 1 2 3

# Monitor range of backtests
docker-compose exec backend python manage.py monitor_backtests 1-10

# Show status without waiting
docker-compose exec backend python manage.py monitor_backtests 1-10 --no-wait

# Custom check interval (default: 5 seconds)
docker-compose exec backend python manage.py monitor_backtests 1-10 --interval 10
```

### Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `backtest_ids` | positional | Backtest IDs to monitor (e.g., "1 2 3" or "1-10") |
| `--no-wait` | flag | Don't wait for completion, just show current status |
| `--interval` | integer | Check interval in seconds (default: 5) |

### Features

1. **Real-time Progress Monitoring**
   - Live status updates every N seconds
   - Counts: completed, running, pending, failed
   - Timestamp for each update
   - Auto-completes when all backtests finish

2. **Comprehensive Report Generation**
   - Groups results by volatility level (HIGH/MEDIUM/LOW)
   - Configuration display (SL/TP multipliers, ADX, confidence)
   - Summary statistics per volatility group
   - Individual backtest results table
   - Best performer highlighting
   - Overall summary across all volatility levels

3. **Volatility-Grouped Analysis**
   - Separate analysis for each volatility category
   - Average metrics: win rate, profit factor, ROI, Sharpe ratio, max drawdown
   - Best performer by profit factor
   - Best performer by win rate

### Output Example

```
Monitoring 9 backtests: [1, 2, 3, 4, 5, 6, 7, 8, 9]

====================================================================================================
MONITORING BACKTEST PROGRESS
====================================================================================================

[16:30:45] Completed: 9/9 | Running: 0 | Pending: 0 | Failed: 0

✅ All backtests completed!

====================================================================================================
COMPREHENSIVE BACKTEST RESULTS REPORT
====================================================================================================

====================================================================================================
HIGH VOLATILITY RESULTS
====================================================================================================

Configuration:
  SL ATR Multiplier: 2.0x
  TP ATR Multiplier: 3.5x
  ADX Threshold: 18.0
  Min Confidence: 70%

Summary Statistics:
  Number of Backtests: 3
  Total Trades: 245
  Average Win Rate: 48.2%
  Average Profit Factor: 2.15
  Average ROI: 15.3%
  Average Sharpe Ratio: 1.85
  Average Max Drawdown: 12.5%

Individual Backtest Results:
----------------------------------------------------------------------------------------------------
Name                                               Trades  Win Rate  P.Factor       ROI     Sharpe
----------------------------------------------------------------------------------------------------
HIGH Volatility - 30 Days - PEPE/SHIB/DOGE            85      49.4%      2.23      18.2%      1.92

🏆 Best Performer (Profit Factor):
  HIGH Volatility - 60 Days - PEPE/SHIB/DOGE
  Win Rate: 50.1%, Profit Factor: 2.35, ROI: 21.5%

====================================================================================================
OVERALL SUMMARY - ALL VOLATILITY LEVELS
====================================================================================================

Total Backtests Completed: 9
Total Trades Executed: 687
Overall Average Win Rate: 52.8%
Overall Average Profit Factor: 2.42
Overall Average ROI: 19.6%
Overall Average Sharpe Ratio: 2.01

====================================================================================================
✅ BACKTEST ANALYSIS COMPLETE
====================================================================================================
```

### Backtest ID Parsing

Supports multiple formats:
- **Individual IDs**: `1 2 3 5 8`
- **Ranges**: `1-10` (expands to 1, 2, 3, ..., 10)
- **Mixed**: `1 2 5-8 10` (expands to 1, 2, 5, 6, 7, 8, 10)

### When to Use

- After queuing multiple backtests
- To track long-running backtest suites
- To generate reports from historical backtests
- To compare performance across volatility levels

### Integration with Backtest System

Works with:
- `BacktestRun` model from `signals.models_backtest`
- Volatility-aware strategy configurations
- Celery async backtest tasks

---

## Command Quick Reference

| Command | Primary Use Case | Time to Run |
|---------|------------------|-------------|
| `analyze_trades` | Diagnose TP/SL issues, check current trade status | < 5 seconds |
| `analyze_performance` | Full performance review with recommendations | < 10 seconds |
| `clean_database` | Fresh start, clear test data | < 30 seconds |
| `create_paper_account` | Setup/update auto-trading account | < 1 second |
| `monitor_backtests` | Track backtest progress, generate reports | Varies (5s-10m+) |

---

## Common Workflows

### Workflow 1: Initial Setup

```bash
# 1. Create paper account
docker-compose exec backend python manage.py create_paper_account --balance 10000

# 2. Wait for trades to generate (signals system running)

# 3. Check trade status
docker-compose exec backend python manage.py analyze_trades

# 4. If TP/SL too far, adjust signal_engine.py and restart
docker-compose restart backend celery-worker
```

### Workflow 2: Performance Analysis

```bash
# 1. Analyze current performance
docker-compose exec backend python manage.py analyze_performance

# 2. Review closed trades
docker-compose exec backend python manage.py analyze_trades --status CLOSED

# 3. If performance good (>50 closed trades), run optimization
# (use ML tuning, walk-forward, monte carlo commands)
```

### Workflow 3: Fresh Start After Parameter Changes

```bash
# 1. Clean database (keep accounts)
docker-compose exec backend python manage.py clean_database --yes --keep-accounts

# 2. Restart services
docker-compose restart backend celery-worker

# 3. Monitor new trades
docker-compose exec backend python manage.py analyze_trades --status ALL

# 4. After 50-100 trades, analyze performance
docker-compose exec backend python manage.py analyze_performance
```

### Workflow 4: Backtest Monitoring

```bash
# 1. Queue backtests (via API or separate script)

# 2. Monitor progress
docker-compose exec backend python manage.py monitor_backtests 1-10

# 3. Report generates automatically when complete
```

---

## Troubleshooting

### Command Not Found

**Error:** `Unknown command: 'analyze_trades'`

**Solutions:**
1. Ensure command file exists: `backend/signals/management/commands/analyze_trades.py`
2. Check `__init__.py` files exist in management directories
3. Restart Django: `docker-compose restart backend`

### Import Errors

**Error:** `ImportError: cannot import name 'PaperTrade'`

**Solutions:**
1. Ensure all migrations are run: `docker-compose exec backend python manage.py migrate`
2. Check models are defined in `signals/models.py`
3. Restart services: `docker-compose restart backend`

### No Data Found

**Error:** `No trades found with status=OPEN`

**Solutions:**
1. Verify paper trading is active
2. Check trade counts: `docker-compose exec backend python manage.py shell -c "from signals.models import PaperTrade; print(PaperTrade.objects.count())"`
3. Try different status: `--status ALL`

### Permission Denied (Database)

**Error:** `PermissionError: [Errno 13] Permission denied`

**Solutions:**
1. Run inside Docker container (not on host)
2. Check database permissions
3. Use `docker-compose exec` not `docker exec`

---

## Best Practices

1. **Always run inside Docker container** using `docker-compose exec backend`
2. **Use --yes flag carefully** for cleanup commands (destructive)
3. **Collect 50-100 closed trades** before running analysis
4. **Monitor trades regularly** to catch TP/SL issues early
5. **Clean database after major parameter changes** for fresh data
6. **Create backups** before cleanup operations
7. **Review recommendations** from analyze_performance before optimization
8. **Use --simple flag** for quick, safe cleanups during development

---

## Related Documentation

- [ANALYZE_TRADES_COMMAND.md](ANALYZE_TRADES_COMMAND.md) - Detailed analyze_trades guide
- [PHASE6_AUTO_OPTIMIZATION_COMPLETE.md](PHASE6_AUTO_OPTIMIZATION_COMPLETE.md) - Auto-optimization system
- [OPTIMIZATION_API_REFERENCE.md](OPTIMIZATION_API_REFERENCE.md) - API endpoints
- [scanner/strategies/signal_engine.py](../backend/scanner/strategies/signal_engine.py) - Trading parameters

---

## Support

For issues or questions:
1. Check command help: `python manage.py <command> --help`
2. Review logs: `docker-compose logs backend`
3. Verify database: `python manage.py shell`
4. Check documentation in `/docs` directory
