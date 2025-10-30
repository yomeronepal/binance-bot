# Walk-Forward Optimization - Execution Flow

## Overview

This document explains **exactly how the walk-forward optimization task executes**, step by step, with code references and data flow diagrams.

---

## Execution Trigger

### User Creates Walk-Forward Run

**Endpoint**: `POST /api/walkforward/`

**User Submits**:
```json
{
  "name": "BTC Strategy Test",
  "symbols": ["BTCUSDT"],
  "timeframe": "5m",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-12-31T23:59:59Z",
  "training_window_days": 90,
  "testing_window_days": 30,
  "step_days": 30,
  "parameter_ranges": {
    "rsi_period": [7, 14, 21],
    "rsi_oversold": [20, 25, 30],
    "rsi_overbought": [70, 75, 80]
  },
  "optimization_method": "grid",
  "initial_capital": 10000,
  "position_size": 100
}
```

**What Happens**:
1. API view validates the request ([views_walkforward.py:48-56](../backend/signals/views_walkforward.py#L48-L56))
2. Creates `WalkForwardOptimization` record with status `PENDING`
3. Queues Celery task: `run_walkforward_optimization_async.delay(walkforward.id)`
4. Returns response with task ID

**File**: [backend/signals/views_walkforward.py:48-85](../backend/signals/views_walkforward.py#L48-L85)

---

## Task Execution Flow

### Phase 1: Initialization (Lines 34-58)

**File**: [backend/scanner/tasks/walkforward_tasks.py:34-58](../backend/scanner/tasks/walkforward_tasks.py#L34-L58)

```python
# 1. Load walk-forward configuration from database
walkforward = WalkForwardOptimization.objects.get(id=walkforward_id)

# 2. Update status to RUNNING
walkforward.status = 'RUNNING'
walkforward.started_at = datetime.now()
walkforward.save()

# 3. Initialize Walk-Forward Engine
wf_engine = WalkForwardEngine()

# 4. Generate time windows
windows = wf_engine.generate_windows(
    walkforward.start_date,          # 2024-01-01
    walkforward.end_date,            # 2024-12-31
    walkforward.training_window_days, # 90 days
    walkforward.testing_window_days,  # 30 days
    walkforward.step_days            # 30 days
)
```

**Output**: List of window configurations
```python
[
    {
        'window_number': 1,
        'training_start': 2024-01-01,
        'training_end': 2024-03-31,    # +90 days
        'testing_start': 2024-04-01,
        'testing_end': 2024-04-30      # +30 days
    },
    {
        'window_number': 2,
        'training_start': 2024-01-31,   # +30 days (step)
        'training_end': 2024-04-30,
        'testing_start': 2024-05-01,
        'testing_end': 2024-05-30
    },
    # ... more windows
]
```

---

### Phase 2: Window Processing Loop (Lines 60-211)

**File**: [backend/scanner/tasks/walkforward_tasks.py:60-211](../backend/scanner/tasks/walkforward_tasks.py#L60-L211)

For each window, the task performs **two phases**:

#### Window Creation (Lines 60-72)

```python
# Create database records for tracking
for window_config in windows:
    window_record = WalkForwardWindow.objects.create(
        walk_forward=walkforward,
        window_number=window_config['window_number'],
        training_start=window_config['training_start'],
        training_end=window_config['training_end'],
        testing_start=window_config['testing_start'],
        testing_end=window_config['testing_end'],
        status='PENDING'
    )
```

---

## Per-Window Execution

### Window Processing Structure

```
For each window (e.g., Window 1):
├── OPTIMIZATION PHASE (In-Sample)
│   ├── Fetch training data (2024-01-01 to 2024-03-31)
│   ├── Run parameter optimization (try all combinations)
│   ├── Select best parameters
│   └── Store in-sample results
│
└── TESTING PHASE (Out-of-Sample)
    ├── Fetch testing data (2024-04-01 to 2024-04-30)
    ├── Apply best parameters to unseen data
    ├── Run backtest with those parameters
    ├── Store out-of-sample results
    └── Calculate performance degradation
```

---

### OPTIMIZATION PHASE (In-Sample) - Lines 84-133

**Status**: Window record set to `OPTIMIZING`

#### Step 1: Fetch Training Data (Lines 88-99)

```python
# Create async event loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Fetch historical price data for training period
historical_fetcher = HistoricalDataFetcher()
symbols_data_train = loop.run_until_complete(
    historical_fetcher.fetch_multiple_symbols(
        symbols=["BTCUSDT"],
        timeframe="5m",
        start_date=2024-01-01,
        end_date=2024-03-31
    )
)
```

**Output**:
```python
{
    "BTCUSDT": [
        {
            'open': 42000.00,
            'high': 42100.00,
            'low': 41900.00,
            'close': 42050.00,
            'volume': 1500.50,
            'timestamp': 2024-01-01 00:00:00
        },
        # ... thousands of 5-minute candles
    ]
}
```

#### Step 2: Run Parameter Optimization (Lines 102-115)

**File**: Uses [scanner/services/parameter_optimizer.py](../backend/scanner/services/parameter_optimizer.py)

```python
optimizer = ParameterOptimizer()
optimization_results = loop.run_until_complete(
    optimizer.optimize_parameters(
        symbols=["BTCUSDT"],
        timeframe="5m",
        start_date=2024-01-01,
        end_date=2024-03-31,
        parameter_ranges={
            'rsi_period': [7, 14, 21],
            'rsi_oversold': [20, 25, 30],
            'rsi_overbought': [70, 75, 80]
        },
        search_method='grid',  # Test all combinations
        initial_capital=10000,
        position_size=100,
        max_combinations=50
    )
)
```

**What `ParameterOptimizer` Does**:
1. Generates all parameter combinations: `3 × 3 × 3 = 27 combinations`
2. For each combination:
   - Generate signals using those parameters
   - Run backtest on training data
   - Calculate performance (ROI, win rate, etc.)
   - Assign optimization score
3. Sort results by score (best first)

**Output**:
```python
[
    {
        'params': {
            'rsi_period': 14,
            'rsi_oversold': 25,
            'rsi_overbought': 75
        },
        'total_trades': 150,
        'win_rate': 62.5,
        'roi': 8.5,
        'sharpe_ratio': 1.8,
        'max_drawdown': 5.2,
        'optimization_score': 95.3  # Highest score
    },
    {
        'params': {
            'rsi_period': 21,
            'rsi_oversold': 20,
            'rsi_overbought': 80
        },
        'total_trades': 120,
        'win_rate': 58.3,
        'roi': 6.2,
        # ... lower score
    },
    # ... more combinations ranked by score
]
```

#### Step 3: Store In-Sample Results (Lines 118-133)

```python
# Get best parameters (first result, already sorted)
best_result = optimization_results[0]
best_params = best_result['params']  # {'rsi_period': 14, ...}

# Save to database
window_record.best_params = best_params
window_record.in_sample_total_trades = 150
window_record.in_sample_win_rate = 62.5
window_record.in_sample_roi = 8.5
window_record.in_sample_sharpe = 1.8
window_record.in_sample_max_drawdown = 5.2
window_record.save()
```

---

### TESTING PHASE (Out-of-Sample) - Lines 135-189

**Status**: Window record set to `TESTING`

**Key Concept**: We now test the best parameters on **UNSEEN DATA** (future period that wasn't used for optimization).

#### Step 1: Fetch Testing Data (Lines 142-149)

```python
# Fetch historical data for TESTING period (future data)
symbols_data_test = loop.run_until_complete(
    historical_fetcher.fetch_multiple_symbols(
        symbols=["BTCUSDT"],
        timeframe="5m",
        start_date=2024-04-01,  # After training period
        end_date=2024-04-30
    )
)
```

#### Step 2: Generate Signals Using Best Parameters (Lines 152-161)

**File**: Uses [scanner/services/signal_engine.py](../backend/scanner/services/signal_engine.py)

```python
# Convert best params to SignalConfig object
signal_config = SignalConfig(
    rsi_period=14,       # Best params from optimization
    rsi_oversold=25,
    rsi_overbought=75
)

# Initialize signal detection engine
engine = SignalDetectionEngine(signal_config)

# Generate signals on testing data
signals = []
for symbol, klines in symbols_data_test.items():
    engine.update_candles(symbol, klines)
    for candle in klines:
        signal = engine.analyze_candle(symbol, candle)
        if signal:
            signals.append(signal)
```

**Output**:
```python
[
    {
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry': 43000.00,
        'sl': 42500.00,
        'tp': 44000.00,
        'timestamp': 2024-04-05 10:30:00
    },
    # ... more signals
]
```

#### Step 3: Run Backtest on Testing Data (Lines 164-169)

**File**: Uses [scanner/services/backtest_engine.py](../backend/scanner/services/backtest_engine.py)

```python
# Initialize backtest engine
backtest_engine = BacktestEngine(
    initial_capital=10000,
    position_size=100
)

# Run backtest with generated signals
test_results = backtest_engine.run_backtest(
    symbols_data_test,  # Testing period data
    signals             # Signals generated with best params
)
```

**What `BacktestEngine` Does**:
1. Simulates taking each trade
2. Tracks entry, exit, P/L
3. Calculates metrics

**Output**:
```python
{
    'total_trades': 85,
    'winning_trades': 45,
    'losing_trades': 40,
    'win_rate': 52.9,  # 45/85 = 52.9% (LOWER than in-sample 62.5%)
    'roi': 4.2,         # 4.2% (LOWER than in-sample 8.5%)
    'sharpe_ratio': 1.2,
    'max_drawdown': 6.8,
    'total_profit_loss': 420.00
}
```

#### Step 4: Store Out-of-Sample Results (Lines 172-189)

```python
# Store out-of-sample results
window_record.out_sample_total_trades = 85
window_record.out_sample_win_rate = 52.9
window_record.out_sample_roi = 4.2
window_record.out_sample_sharpe = 1.2
window_record.out_sample_max_drawdown = 6.8

# Calculate performance degradation
in_roi = 8.5   # In-sample ROI
out_roi = 4.2  # Out-of-sample ROI

performance_drop = ((8.5 - 4.2) / 8.5) * 100 = 50.6%

window_record.performance_drop_pct = 50.6
window_record.status = 'COMPLETED'
window_record.save()
```

**Interpretation**:
- In-sample ROI: 8.5% (optimized on training data)
- Out-of-sample ROI: 4.2% (tested on unseen data)
- Performance drop: 50.6% (indicates moderate overfitting)

---

### Phase 3: Aggregate Results (Lines 213-230)

**File**: [backend/scanner/tasks/walkforward_tasks.py:213-230](../backend/scanner/tasks/walkforward_tasks.py#L213-L230)

After all windows are processed:

```python
# Collect results from all windows
window_results = [
    {
        'window_number': 1,
        'in_sample_roi': 8.5,
        'out_sample_roi': 4.2,
        'in_sample_win_rate': 62.5,
        'out_sample_win_rate': 52.9
    },
    {
        'window_number': 2,
        'in_sample_roi': 7.8,
        'out_sample_roi': 3.9,
        # ...
    },
    # ... all windows
]

# Calculate aggregate metrics
aggregate_metrics = wf_engine.calculate_aggregate_metrics(window_results)
```

**File**: [scanner/services/walkforward_engine.py](../backend/scanner/services/walkforward_engine.py)

**`calculate_aggregate_metrics()` Does**:

1. **Calculate Averages**:
```python
avg_in_sample_roi = mean([8.5, 7.8, 9.2, ...]) = 8.2%
avg_out_sample_roi = mean([4.2, 3.9, 4.5, ...]) = 4.1%
```

2. **Calculate Performance Degradation**:
```python
performance_degradation = ((8.2 - 4.1) / 8.2) * 100 = 50.0%
```

3. **Calculate Consistency Score** (using coefficient of variation):
```python
out_sample_rois = [4.2, 3.9, 4.5, 3.8, 4.3]
mean_roi = 4.14
std_roi = 0.27
cv = 0.27 / 4.14 = 0.065  # Low variation = good consistency

# Convert to 0-100 score
consistency_score = 95  # CV < 0.25 = excellent
```

4. **Assess Robustness** (4 criteria check):
```python
✅ Out-of-sample ROI positive? 4.1% > 0 ✓
⚠️ Performance degradation acceptable? 50.0% > 50% ✗ (marginal)
✅ Consistency score good? 95 > 40 ✓
✅ Profitable windows? 8/10 = 80% > 50% ✓

Verdict: ⚠️ MARGINAL (3/4 criteria pass, but high degradation)
```

**Output**:
```python
{
    'avg_in_sample_roi': 8.2,
    'avg_out_sample_roi': 4.1,
    'performance_degradation': 50.0,
    'consistency_score': 95,
    'is_robust': False,  # Failed due to high degradation
    'robustness_notes': '⚠️ MARGINAL - High performance degradation (50.0%) indicates overfitting...'
}
```

---

### Phase 4: Completion (Lines 228-243)

```python
# Update walk-forward record with final results
walkforward.avg_in_sample_roi = 8.2
walkforward.avg_out_sample_roi = 4.1
walkforward.performance_degradation = 50.0
walkforward.consistency_score = 95
walkforward.is_robust = False
walkforward.robustness_notes = '⚠️ MARGINAL - ...'

walkforward.status = 'COMPLETED'
walkforward.completed_at = datetime.now()
walkforward.save()

# Log results
logger.info(f"✅ Walk-forward optimization completed!")
logger.info(f"  Average Out-of-Sample ROI: 4.1%")
logger.info(f"  Consistency Score: 95/100")
logger.info(f"  Robust: ❌ NO")

# Return results
return {
    'walkforward_id': walkforward_id,
    'status': 'COMPLETED',
    'is_robust': False,
    'avg_out_sample_roi': 4.1,
    'consistency_score': 95
}
```

---

## Data Flow Visualization

```
USER REQUEST
    ↓
POST /api/walkforward/
    ↓
Create WalkForwardOptimization (status: PENDING)
    ↓
Queue Celery Task: run_walkforward_optimization_async.delay(id)
    ↓
═══════════════════════════════════════════════════════
CELERY WORKER PICKS UP TASK
═══════════════════════════════════════════════════════
    ↓
Update status: RUNNING
    ↓
Generate Windows (e.g., 10 windows)
    ↓
Create WalkForwardWindow records (10 records, status: PENDING)
    ↓
┌─────────────────────────────────────────────────────┐
│ FOR EACH WINDOW (1 through 10)                      │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌────────────────────────────────────────┐        │
│  │ OPTIMIZATION PHASE (In-Sample)         │        │
│  ├────────────────────────────────────────┤        │
│  │ Status: OPTIMIZING                      │        │
│  │                                         │        │
│  │ 1. Fetch training data                 │        │
│  │    (e.g., 2024-01-01 to 2024-03-31)   │        │
│  │                                         │        │
│  │ 2. Run ParameterOptimizer              │        │
│  │    - Try 27 parameter combinations     │        │
│  │    - Backtest each on training data    │        │
│  │    - Rank by optimization score        │        │
│  │                                         │        │
│  │ 3. Select best parameters              │        │
│  │    {'rsi_period': 14, ...}            │        │
│  │                                         │        │
│  │ 4. Store in-sample results             │        │
│  │    - ROI: 8.5%                         │        │
│  │    - Win Rate: 62.5%                   │        │
│  │    - Trades: 150                       │        │
│  └────────────────────────────────────────┘        │
│                  ↓                                   │
│  ┌────────────────────────────────────────┐        │
│  │ TESTING PHASE (Out-of-Sample)          │        │
│  ├────────────────────────────────────────┤        │
│  │ Status: TESTING                         │        │
│  │                                         │        │
│  │ 1. Fetch testing data (UNSEEN)         │        │
│  │    (e.g., 2024-04-01 to 2024-04-30)   │        │
│  │                                         │        │
│  │ 2. Generate signals                     │        │
│  │    Using best params from optimization │        │
│  │                                         │        │
│  │ 3. Run BacktestEngine                  │        │
│  │    Simulate trades on testing data     │        │
│  │                                         │        │
│  │ 4. Store out-of-sample results         │        │
│  │    - ROI: 4.2%                         │        │
│  │    - Win Rate: 52.9%                   │        │
│  │    - Trades: 85                        │        │
│  │                                         │        │
│  │ 5. Calculate performance drop          │        │
│  │    (8.5 - 4.2) / 8.5 = 50.6%          │        │
│  └────────────────────────────────────────┘        │
│                  ↓                                   │
│  Update WalkForwardWindow (status: COMPLETED)       │
│  Update progress counter                            │
│                                                      │
└─────────────────────────────────────────────────────┘
    ↓
═══════════════════════════════════════════════════════
AFTER ALL WINDOWS COMPLETE
═══════════════════════════════════════════════════════
    ↓
Calculate Aggregate Metrics
    ├─ Average in-sample ROI: 8.2%
    ├─ Average out-of-sample ROI: 4.1%
    ├─ Performance degradation: 50.0%
    ├─ Consistency score: 95/100
    └─ Robustness assessment: ⚠️ MARGINAL
    ↓
Update WalkForwardOptimization
    ├─ Store aggregate metrics
    ├─ Store robustness verdict
    └─ Set status: COMPLETED
    ↓
Return results to user
```

---

## Key Services Used

### 1. HistoricalDataFetcher
**File**: [backend/scanner/services/historical_data_fetcher.py](../backend/scanner/services/historical_data_fetcher.py)

**Purpose**: Fetch historical candlestick data from Binance API

**Method**: `fetch_multiple_symbols(symbols, timeframe, start_date, end_date)`

**Returns**: Dict of symbol → list of OHLCV candles

---

### 2. ParameterOptimizer
**File**: [backend/scanner/services/parameter_optimizer.py](../backend/scanner/services/parameter_optimizer.py)

**Purpose**: Test all parameter combinations to find best settings

**Method**: `optimize_parameters(symbols, timeframe, start_date, end_date, parameter_ranges, ...)`

**Returns**: List of results sorted by optimization score (best first)

**Process**:
1. Generate all combinations from parameter ranges
2. For each combination:
   - Generate signals using those parameters
   - Run backtest
   - Calculate optimization score
3. Sort by score
4. Return ranked list

---

### 3. SignalDetectionEngine
**File**: [backend/scanner/services/signal_engine.py](../backend/scanner/services/signal_engine.py)

**Purpose**: Generate trading signals using technical analysis

**Methods**:
- `update_candles(symbol, candles)` - Update internal state
- `analyze_candle(symbol, candle)` - Analyze single candle for signal

**Returns**: Signal object with entry/SL/TP or None

---

### 4. BacktestEngine
**File**: [backend/scanner/services/backtest_engine.py](../backend/scanner/services/backtest_engine.py)

**Purpose**: Simulate trading with given signals and calculate metrics

**Method**: `run_backtest(symbols_data, signals)`

**Returns**: Dict with performance metrics (ROI, win rate, trades, etc.)

**Process**:
1. Iterate through signals chronologically
2. Simulate opening positions
3. Track P/L when SL/TP hit
4. Calculate aggregate metrics

---

### 5. WalkForwardEngine
**File**: [backend/scanner/services/walkforward_engine.py](../backend/scanner/services/walkforward_engine.py)

**Purpose**: Walk-forward analysis logic and calculations

**Methods**:
- `generate_windows()` - Create rolling window configurations
- `calculate_aggregate_metrics()` - Aggregate all window results
- `calculate_performance_degradation()` - Measure overfitting
- `calculate_consistency_score()` - Measure result consistency
- `assess_robustness()` - Evaluate strategy robustness

---

## Example Timeline

Let's walk through a real example:

**Configuration**:
- Symbols: BTCUSDT
- Date Range: 2024-01-01 to 2024-12-31 (365 days)
- Training Window: 90 days
- Testing Window: 30 days
- Step: 30 days

**Windows Generated**: 10 windows

| Window | Training Period      | Testing Period       |
|--------|---------------------|---------------------|
| 1      | Jan 1 - Mar 31      | Apr 1 - Apr 30      |
| 2      | Jan 31 - Apr 30     | May 1 - May 30      |
| 3      | Mar 1 - May 31      | Jun 1 - Jun 30      |
| 4      | Mar 31 - Jun 30     | Jul 1 - Jul 31      |
| 5      | Apr 30 - Jul 31     | Aug 1 - Aug 31      |
| 6      | May 30 - Aug 31     | Sep 1 - Sep 30      |
| 7      | Jun 30 - Sep 30     | Oct 1 - Oct 31      |
| 8      | Jul 31 - Oct 31     | Nov 1 - Nov 30      |
| 9      | Aug 31 - Nov 30     | Dec 1 - Dec 31      |
| 10     | Sep 30 - Dec 31     | Jan 1 - Jan 31 (2025)|

**Execution Time**: ~2-5 hours (depends on parameter combinations and data size)

**Process per Window** (~12-30 minutes each):
1. Fetch training data: 2-3 minutes
2. Optimize parameters (27 combinations): 5-20 minutes
3. Fetch testing data: 2-3 minutes
4. Run backtest: 2-3 minutes
5. Store results: < 1 minute

---

## Error Handling

### Window-Level Errors (Lines 206-211)

If a window fails (e.g., API timeout, insufficient data):

```python
except Exception as e:
    logger.error(f"Error processing window {window_number}: {e}")
    window_record.status = 'FAILED'
    window_record.error_message = str(e)
    window_record.save()
    continue  # Move to next window
```

**Behavior**: Task continues with remaining windows instead of failing entirely.

### Task-Level Errors (Lines 245-257)

If entire task fails:

```python
except Exception as e:
    logger.error(f"Error in walk-forward optimization: {e}")

    # Update status to FAILED
    walkforward.status = 'FAILED'
    walkforward.error_message = str(e)
    walkforward.completed_at = datetime.now()
    walkforward.save()

    # Retry once after 60 seconds
    raise self.retry(exc=e, countdown=60)
```

---

## Progress Tracking

Users can monitor progress via API:

```bash
GET /api/walkforward/:id/
```

**Response**:
```json
{
  "id": 1,
  "status": "RUNNING",
  "total_windows": 10,
  "completed_windows": 6,
  "progress_percentage": 60
}
```

Frontend can poll this endpoint every 5-10 seconds to show progress bar.

---

## Summary

**Walk-Forward Optimization Task Execution**:

1. **Triggered** when user creates walk-forward via API
2. **Queued** as Celery background task
3. **Generates** rolling time windows
4. **For each window**:
   - Optimizes parameters on training data (in-sample)
   - Tests best parameters on future data (out-of-sample)
   - Records performance drop
5. **Aggregates** results from all windows
6. **Assesses** robustness using 4 criteria
7. **Returns** verdict with detailed metrics

**Key Insight**: By testing on multiple out-of-sample periods, walk-forward optimization reveals whether a strategy is genuinely robust or just overfit to historical data.

---

**File References**:
- Task: [backend/scanner/tasks/walkforward_tasks.py](../backend/scanner/tasks/walkforward_tasks.py)
- Engine: [backend/scanner/services/walkforward_engine.py](../backend/scanner/services/walkforward_engine.py)
- API: [backend/signals/views_walkforward.py](../backend/signals/views_walkforward.py)
- Models: [backend/signals/models_walkforward.py](../backend/signals/models_walkforward.py)
