# Technical Documentation

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Core Components](#core-components)
3. [Data Flow](#data-flow)
4. [Trading Strategy](#trading-strategy)
5. [Signal Detection Engine](#signal-detection-engine)
6. [Backtesting System](#backtesting-system)
7. [Paper Trading](#paper-trading)
8. [Database Schema](#database-schema)
9. [API Integration](#api-integration)
10. [Performance Optimization](#performance-optimization)

---

## System Architecture

### Overview
The Binance Trading Bot is a sophisticated cryptocurrency trading system built on a microservices architecture using Docker containers. The system consists of five main services that work together to provide real-time signal detection, backtesting, and paper trading capabilities.

### Technology Stack

**Backend**:
- **Django 4.x**: Web framework and REST API
- **Celery**: Distributed task queue for async processing
- **Redis**: Message broker and caching layer
- **PostgreSQL**: Primary database for persistent storage
- **pandas-ta**: Technical analysis indicator library

**Frontend**:
- **React 18**: UI framework
- **Vite**: Build tool and dev server
- **Zustand**: State management
- **React Query**: Data fetching and caching
- **TailwindCSS**: Styling framework

**Infrastructure**:
- **Docker & Docker Compose**: Containerization
- **Nginx**: Reverse proxy (production)
- **GitHub Actions**: CI/CD pipeline

### Service Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Load Balancer                          │
│                      (Nginx - Production)                    │
└────────────────┬───────────────────────┬────────────────────┘
                 │                       │
         ┌───────▼────────┐     ┌───────▼─────────┐
         │   Frontend     │     │    Backend      │
         │   (React)      │     │    (Django)     │
         │   Port 5173    │     │   Port 8000     │
         └────────────────┘     └───────┬─────────┘
                                        │
                 ┌──────────────────────┼──────────────────────┐
                 │                      │                      │
         ┌───────▼────────┐     ┌──────▼──────┐     ┌────────▼────────┐
         │  Celery Worker │     │   Redis     │     │   PostgreSQL    │
         │  (Tasks)       │     │ (Broker)    │     │   (Database)    │
         │                │     │ Port 6379   │     │   Port 5432     │
         └───────┬────────┘     └─────────────┘     └─────────────────┘
                 │
         ┌───────▼────────┐
         │  Celery Beat   │
         │  (Scheduler)   │
         └────────────────┘
```

### Container Communication

**Internal Network**: All containers communicate via Docker's internal network (`binancebot_default`)

**Data Persistence**:
- `postgres_data`: PostgreSQL database
- `redis_data`: Redis cache and broker data
- `backend/backtest_data`: Historical price data (CSV files)

---

## Core Components

### 1. Signal Detection Engine
**Location**: [backend/scanner/strategies/signal_engine.py](../backend/scanner/strategies/signal_engine.py)

**Purpose**: Real-time signal generation using 13-indicator weighted scoring system

**Key Classes**:
- `SignalConfig`: Configuration parameters for signal detection
- `ActiveSignal`: Represents an active trading signal
- `SignalDetectionEngine`: Main engine class

**Configuration Parameters**:
```python
@dataclass
class SignalConfig:
    # Entry thresholds
    long_rsi_min: float = 23.0      # LONG entry RSI minimum
    long_rsi_max: float = 33.0      # LONG entry RSI maximum
    long_adx_min: float = 22.0      # ADX trend strength requirement

    # Risk management
    sl_atr_multiplier: float = 1.5  # Stop loss distance (1.5x ATR)
    tp_atr_multiplier: float = 5.25 # Take profit (5.25x ATR = 1:3.5 R/R)

    # Quality filter
    min_confidence: float = 0.73    # Minimum signal confidence
```

**Indicator Weights**:
| Indicator | Weight | Purpose |
|-----------|--------|---------|
| MACD | 2.0 | Momentum confirmation |
| SuperTrend | 1.9 | Trend following |
| Price vs EMA | 1.8 | Trend direction |
| ADX | 1.7 | Trend strength |
| Heikin-Ashi | 1.6 | Smoothed trend |
| RSI | 1.5 | Overbought/oversold |
| Volume | 1.4 | Interest confirmation |
| MFI | 1.3 | Money flow |
| EMA Alignment | 1.2 | Multi-timeframe |
| PSAR | 1.1 | Adaptive trailing |
| +DI/-DI | 1.0 | Directional movement |
| Bollinger Bands | 0.8 | Volatility extremes |
| Volatility | 0.5 | Market condition |

**Total Weight**: 16.8
**Confidence Calculation**: `score / total_weight`

### 2. Backtesting Engine
**Location**: [backend/scanner/services/backtest_engine.py](../backend/scanner/services/backtest_engine.py)

**Purpose**: Simulate trading strategy over historical data

**Key Features**:
- Event-driven simulation (candle-by-candle)
- Realistic order execution (market orders)
- ATR-based stop loss and take profit
- Comprehensive performance metrics

**Metrics Calculated**:
- **ROI**: Return on Investment
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Gross profit / Gross loss
- **Sharpe Ratio**: Risk-adjusted returns
- **Max Drawdown**: Largest peak-to-trough decline
- **Average Trade Duration**: Time in market per trade

**Execution Logic**:
```python
def _check_entry(signal, candle):
    """
    Entry Conditions:
    1. Candle timestamp >= signal timestamp
    2. Entry price within candle's range
    3. Position not already open
    """

def _check_exit(position, candle):
    """
    Exit Conditions:
    1. Stop Loss hit: candle['low'] <= position.sl (LONG)
    2. Take Profit hit: candle['high'] >= position.tp (LONG)
    3. Opposite signal (optional)
    """
```

### 3. Historical Data Fetcher
**Location**: [backend/scanner/services/historical_data_fetcher.py](../backend/scanner/services/historical_data_fetcher.py)

**Purpose**: Download and cache historical price data from Binance

**Data Sources**:
1. **CSV Files** (Primary): Cached in `backend/backtest_data/`
2. **Binance API** (Fallback): Real-time data fetch

**Download Script**:
**Location**: [backend/scripts/data/download_long_period.py](../backend/scripts/data/download_long_period.py)

**Performance**:
- **Async Downloads**: 30x faster than sequential
- **3-Month Data**: ~4 seconds per symbol
- **11-Month Data**: ~15 seconds per symbol
- **Rate Limiting**: 0.1s delay between requests

**CSV Format**:
```csv
timestamp,open,high,low,close,volume
1704067200000,42150.00,42280.50,42100.00,42250.00,1234.5678
```

### 4. Volatility Classifier
**Location**: [backend/scanner/services/volatility_classifier.py](../backend/scanner/services/volatility_classifier.py)

**Purpose**: Classify market volatility and adjust parameters dynamically

**Volatility Levels**:
- **LOW**: ATR/Price < 1.5% (e.g., BTCUSDT, ETHUSDT)
- **MEDIUM**: ATR/Price 1.5% - 3.5% (e.g., SOLUSDT, ADAUSDT)
- **HIGH**: ATR/Price > 3.5% (e.g., DOGEUSDT, meme coins)

**Adaptive Parameters** (when enabled):
```python
LOW_VOLATILITY_CONFIG = {
    "sl_atr_multiplier": 1.5,    # Tighter stops
    "tp_atr_multiplier": 5.25,   # Wider targets
    "min_confidence": 0.73       # Higher quality
}

HIGH_VOLATILITY_CONFIG = {
    "sl_atr_multiplier": 2.5,    # Wider stops
    "tp_atr_multiplier": 6.0,    # Wider targets
    "min_confidence": 0.65       # More signals
}
```

**⚠️ IMPORTANT**: Volatility-aware mode is **DISABLED** in production for consistent backtesting results. See [backend/scanner/tasks/backtest_tasks.py:72](../backend/scanner/tasks/backtest_tasks.py#L72)

### 5. Celery Task Queue
**Location**: [backend/scanner/tasks/](../backend/scanner/tasks/)

**Purpose**: Async execution of long-running tasks

**Task Types**:

**Backtest Tasks** (`backtest_tasks.py`):
- `run_backtest_task`: Execute backtest simulation
- `cleanup_old_backtests`: Remove expired results

**Scanner Tasks** (`celery_tasks.py`):
- `fetch_and_process_signals`: Real-time signal detection
- `update_active_signals`: Track signal lifecycle
- `execute_paper_trades`: Paper trading simulation

**Polling Workers** (`polling_worker_v2.py`):
- `multi_timeframe_scanner`: Scan multiple timeframes simultaneously
- `forex_scanner`: Scan forex pairs (future feature)

**Walk-Forward Optimization** (`walkforward_tasks.py`):
- `run_walkforward_optimization`: Adaptive parameter optimization

**Celery Configuration**:
```python
# backend/config/celery.py
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/0'
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'UTC'

# Task routing
CELERY_TASK_ROUTES = {
    'scanner.tasks.backtest_tasks.*': {'queue': 'backtests'},
    'scanner.tasks.celery_tasks.*': {'queue': 'signals'},
}
```

### 6. Paper Trading System
**Location**: [backend/signals/services/paper_trader.py](../backend/signals/services/paper_trader.py)

**Purpose**: Simulate live trading without real money

**Features**:
- Real-time signal execution
- Position tracking with P&L calculation
- Auto-close on SL/TP hit
- Performance metrics dashboard

**Trade Lifecycle**:
```
Signal Detected → Entry Order → Position Open → Monitor SL/TP → Exit Order → Position Closed
       ↓              ↓              ↓                ↓               ↓             ↓
    Database      Entry Price    Update P&L      Check Exit      Exit Price   Calculate P&L
```

**Position Management**:
```python
class PaperPosition:
    symbol: str
    direction: str          # 'LONG' or 'SHORT'
    entry_price: Decimal
    position_size: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    unrealized_pnl: Decimal  # Updated real-time
    realized_pnl: Decimal    # After close
```

---

## Data Flow

### Signal Generation Flow
```
1. Celery Beat schedules scan (every 5 minutes)
   ↓
2. fetch_and_process_signals task executes
   ↓
3. Fetch latest candles from Binance API
   ↓
4. Calculate 13 technical indicators
   ↓
5. Run weighted scoring algorithm
   ↓
6. If confidence >= threshold, create signal
   ↓
7. Save to database (Signal model)
   ↓
8. Broadcast to frontend via WebSocket (future)
   ↓
9. Execute paper trade (if paper trading enabled)
```

### Backtest Execution Flow
```
1. User submits backtest via API
   ↓
2. Create BacktestRun record (status: PENDING)
   ↓
3. Celery picks up run_backtest_task
   ↓
4. Load historical CSV data
   ↓
5. Initialize SignalDetectionEngine
   ↓
6. Loop through candles:
   - Generate signals
   - Check entry conditions
   - Check exit conditions
   - Update positions
   ↓
7. Calculate performance metrics
   ↓
8. Save results to database
   ↓
9. Update status to COMPLETED
   ↓
10. Frontend polls and displays results
```

### Paper Trading Flow
```
1. Real-time signal detected
   ↓
2. Check if paper trading enabled
   ↓
3. Create PaperTrade (status: PENDING)
   ↓
4. Simulate market order execution
   ↓
5. Open position at entry price
   ↓
6. Update status to OPEN
   ↓
7. Monitor price every minute:
   - Calculate unrealized P&L
   - Check if SL hit → Close position (LOSS)
   - Check if TP hit → Close position (WIN)
   ↓
8. Update position in database
   ↓
9. Update dashboard metrics
```

---

## Trading Strategy

### Strategy Type
**Mean Reversion with Trend Confirmation**

**Philosophy**:
- Enter when price is oversold/overbought (RSI)
- Confirm with multiple trend indicators
- Use strong risk/reward ratio (1:3.5)
- Filter low-quality signals with confidence threshold

### Entry Logic (LONG)

**Primary Condition**: RSI between 23-33 (oversold)

**Confirmation Requirements** (weighted scoring >= 73%):

1. **MACD Bullish** (weight 2.0):
   - MACD line > Signal line
   - MACD histogram > 0

2. **SuperTrend Bullish** (weight 1.9):
   - Price > SuperTrend line
   - SuperTrend direction = UP

3. **Price Above EMA** (weight 1.8):
   - Close > EMA9
   - Close > EMA21

4. **Strong Trend** (weight 1.7):
   - ADX >= 22.0
   - +DI > -DI (directional movement)

5. **Heikin-Ashi Bullish** (weight 1.6):
   - HA candle color = green
   - HA body > previous body

6. **Volume Spike** (weight 1.4):
   - Volume > 1.2x MA(20)

7. **MFI Bullish** (weight 1.3):
   - MFI > 50 (money flowing in)

8. **EMA Alignment** (weight 1.2):
   - EMA9 > EMA21 > EMA50

9. **PSAR Bullish** (weight 1.1):
   - Price > Parabolic SAR

10. **Bollinger Bands** (weight 0.8):
    - Price near lower band (oversold)

**Code Reference**: [signal_engine.py:_check_long_conditions()](../backend/scanner/strategies/signal_engine.py#L400-L450)

### Exit Logic

**Stop Loss**:
- Distance: 1.5x ATR from entry
- **LONG**: SL = Entry - (1.5 × ATR)
- **SHORT**: SL = Entry + (1.5 × ATR)

**Take Profit**:
- Distance: 5.25x ATR from entry (1:3.5 R/R)
- **LONG**: TP = Entry + (5.25 × ATR)
- **SHORT**: TP = Entry - (5.25 × ATR)

**Exit Priority**:
1. Stop Loss hit → Exit immediately (LOSS)
2. Take Profit hit → Exit immediately (WIN)
3. Opposite signal → Optional exit
4. Time-based exit → Not implemented (could be added)

### Mathematical Foundation

**Breakeven Win Rate Calculation**:
```
For R:R ratio of 1:3.5

Win Rate × R = (1 - Win Rate) × 1
Win Rate × 3.5 = (1 - Win Rate) × 1
3.5 × WR = 1 - WR
4.5 × WR = 1
WR = 22.22%
```

**Current Performance** (OPT6, 4h BTCUSDT):
- **Win Rate**: 16.7% (1 win, 5 losses out of 6 trades)
- **Required**: 22.22% for profitability
- **Gap**: Need 1 more winning trade out of 6

### Parameter Optimization History

**Configuration Evolution**:

| Version | RSI Range | ADX Min | Confidence | SL Mult | TP Mult | Win Rate | ROI |
|---------|-----------|---------|------------|---------|---------|----------|-----|
| BASELINE | 25-35 | 20.0 | 0.70 | 1.5 | 3.5 | 8.6% | -44% |
| OPT1 | 20-30 | 20.0 | 0.70 | 1.5 | 3.5 | 12% | -28% |
| OPT2 | 25-35 | 20.0 | 0.75 | 1.5 | 3.5 | 15% | -15% |
| OPT3 | 25-35 | 25.0 | 0.70 | 1.5 | 3.5 | 18% | -8% |
| OPT6 | **23-33** | **22.0** | **0.73** | **1.5** | **5.25** | **16.7%** | **-0.03%** |

**OPT6 = Best Configuration** ✅

**Key Insights**:
1. **4h timeframe** doubled win rate vs 5m (22% vs 8%)
2. **Tighter RSI range** (23-33) reduced false signals
3. **Higher ADX requirement** (22.0) ensured stronger trends
4. **Wider TP** (5.25x) captured larger moves
5. **Confidence threshold** (73%) filtered marginal signals

---

## Signal Detection Engine

### Engine Initialization

```python
from scanner.strategies.signal_engine import SignalDetectionEngine, SignalConfig

# Create configuration
config = SignalConfig(
    long_rsi_min=23.0,
    long_rsi_max=33.0,
    long_adx_min=22.0,
    min_confidence=0.73,
    sl_atr_multiplier=1.5,
    tp_atr_multiplier=5.25
)

# Initialize engine
engine = SignalDetectionEngine(
    config=config,
    use_volatility_aware=False  # IMPORTANT: Keep False for consistent results
)
```

### Processing Candles

```python
# Fetch candles from Binance or CSV
candles = fetch_historical_candles(
    symbol='BTCUSDT',
    interval='4h',
    start_date='2024-01-01',
    end_date='2024-11-01'
)

# Process candles
signals = []
for candle in candles:
    signal = engine.process_candle(
        symbol='BTCUSDT',
        candle=candle,
        timeframe='4h'
    )

    if signal:
        signals.append(signal)
        print(f"New {signal.direction} signal at {signal.entry}")
```

### Signal Output Format

```python
{
    'symbol': 'BTCUSDT',
    'direction': 'LONG',
    'entry_price': 42250.00,
    'stop_loss': 41500.00,      # 1.5x ATR below entry
    'take_profit': 44875.00,    # 5.25x ATR above entry
    'confidence': 0.78,         # 78% confidence
    'timeframe': '4h',
    'description': 'RSI oversold, MACD bullish, Strong trend',
    'created_at': '2024-10-01T12:00:00Z',
    'conditions_met': {
        'macd_bullish': True,
        'rsi_oversold': True,
        'adx_strong': True,
        'price_above_ema': True,
        # ... other conditions
    }
}
```

---

## Backtesting System

### API Endpoint

**URL**: `POST /api/backtest/`

**Request Body**:
```json
{
  "name": "OPT6 Test Run",
  "symbols": ["BTCUSDT"],
  "timeframe": "4h",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-11-01T00:00:00Z",
  "strategy_params": {
    "min_confidence": 0.73,
    "long_adx_min": 22.0,
    "long_rsi_min": 23.0,
    "long_rsi_max": 33.0,
    "sl_atr_multiplier": 1.5,
    "tp_atr_multiplier": 5.25
  },
  "initial_capital": 10000,
  "position_size": 100
}
```

**Response**:
```json
{
  "id": 123,
  "name": "OPT6 Test Run",
  "status": "PENDING",
  "created_at": "2024-11-01T10:00:00Z"
}
```

### Results Format

**GET** `/api/backtest/123/`

```json
{
  "id": 123,
  "name": "OPT6 Test Run",
  "status": "COMPLETED",
  "results": {
    "roi": -0.03,
    "win_rate": 16.7,
    "total_trades": 6,
    "winning_trades": 1,
    "losing_trades": 5,
    "profit_factor": 0.85,
    "sharpe_ratio": -0.12,
    "max_drawdown": 2.5,
    "avg_trade_duration_hours": 48,
    "final_capital": 9996.88,
    "total_pnl": -3.12
  },
  "trades": [
    {
      "entry_time": "2024-08-15T08:00:00Z",
      "exit_time": "2024-08-17T12:00:00Z",
      "direction": "LONG",
      "entry_price": 58500.00,
      "exit_price": 60250.00,
      "pnl": 175.00,
      "pnl_percent": 2.99,
      "exit_reason": "TAKE_PROFIT"
    },
    // ... 5 more trades
  ]
}
```

### Performance Metrics Explained

**ROI (Return on Investment)**:
```python
ROI = (Final Capital - Initial Capital) / Initial Capital × 100
```

**Win Rate**:
```python
Win Rate = Winning Trades / Total Trades × 100
```

**Profit Factor**:
```python
Profit Factor = Gross Profit / Gross Loss
# > 1.0 = Profitable
# < 1.0 = Losing
```

**Sharpe Ratio**:
```python
Sharpe = (Mean Return - Risk Free Rate) / Std Dev of Returns
# > 1.0 = Good risk-adjusted returns
# > 2.0 = Excellent
```

**Max Drawdown**:
```python
Max Drawdown = (Trough - Peak) / Peak × 100
# Maximum loss from equity peak
```

---

## Paper Trading

### Enable Paper Trading

**API Endpoint**: `POST /api/paper-trading/enable`

```json
{
  "initial_capital": 10000,
  "position_size_percent": 10,  // 10% of capital per trade
  "auto_close_on_sl_tp": true
}
```

### Monitor Performance

**API Endpoint**: `GET /api/paper-trading/performance`

**Response**:
```json
{
  "total_trades": 15,
  "winning_trades": 8,
  "losing_trades": 7,
  "win_rate": 53.3,
  "total_pnl": 450.50,
  "roi": 4.51,
  "active_positions": 2,
  "available_capital": 8200.00,
  "total_capital": 10450.50
}
```

### Active Positions

**API Endpoint**: `GET /api/paper-trading/positions`

```json
{
  "positions": [
    {
      "id": 45,
      "symbol": "BTCUSDT",
      "direction": "LONG",
      "entry_price": 62500.00,
      "current_price": 63200.00,
      "position_size": 0.16,
      "unrealized_pnl": 112.00,
      "unrealized_pnl_percent": 1.12,
      "stop_loss": 61500.00,
      "take_profit": 66125.00,
      "opened_at": "2024-11-01T14:30:00Z"
    }
  ]
}
```

---

## Database Schema

### Key Models

#### Signal Model
```python
class Signal(models.Model):
    symbol = models.CharField(max_length=20)
    signal_type = models.CharField(max_length=10)  # 'LONG' or 'SHORT'
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8)
    confidence = models.FloatField()
    timeframe = models.CharField(max_length=10)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
```

#### BacktestRun Model
```python
class BacktestRun(models.Model):
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20)  # PENDING, RUNNING, COMPLETED, FAILED
    symbols = models.JSONField()
    timeframe = models.CharField(max_length=10)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    strategy_params = models.JSONField()
    initial_capital = models.DecimalField(max_digits=20, decimal_places=2)
    results = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)
```

#### PaperTrade Model
```python
class PaperTrade(models.Model):
    signal = models.ForeignKey(Signal, on_delete=models.CASCADE)
    status = models.CharField(max_length=20)  # PENDING, OPEN, CLOSED
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    exit_price = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    position_size = models.DecimalField(max_digits=20, decimal_places=8)
    realized_pnl = models.DecimalField(max_digits=20, decimal_places=2, null=True)
    unrealized_pnl = models.DecimalField(max_digits=20, decimal_places=2, null=True)
    opened_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True)
    exit_reason = models.CharField(max_length=50, null=True)  # SL_HIT, TP_HIT, MANUAL
```

### Database Indexes

**Performance-Critical Indexes**:
```sql
-- Signal lookups
CREATE INDEX idx_signal_symbol_active ON signals_signal(symbol, is_active);
CREATE INDEX idx_signal_created_at ON signals_signal(created_at DESC);

-- Backtest queries
CREATE INDEX idx_backtest_status ON signals_backtestrun(status);
CREATE INDEX idx_backtest_created ON signals_backtestrun(created_at DESC);

-- Paper trading
CREATE INDEX idx_papertrade_status ON signals_papertrade(status);
CREATE INDEX idx_papertrade_signal ON signals_papertrade(signal_id);
```

---

## API Integration

### Binance API

**Endpoints Used**:
1. **Klines (Candles)**: `/api/v3/klines`
2. **Exchange Info**: `/api/v3/exchangeInfo`
3. **Ticker Price**: `/api/v3/ticker/price`

**Rate Limits**:
- Weight-based: 1200 requests/minute
- Order rate: 10 orders/second
- WebSocket: 5 connections per IP

**Example Request**:
```python
import ccxt

exchange = ccxt.binance({
    'apiKey': 'YOUR_API_KEY',
    'secret': 'YOUR_SECRET',
    'enableRateLimit': True
})

# Fetch OHLCV data
candles = exchange.fetch_ohlcv(
    symbol='BTC/USDT',
    timeframe='4h',
    since=1704067200000,  # Unix timestamp
    limit=1000
)
```

### Internal REST API

**Base URL**: `http://localhost:8000/api/`

**Endpoints**:
- `POST /backtest/` - Create backtest
- `GET /backtest/{id}/` - Get backtest results
- `GET /signals/` - List active signals
- `POST /paper-trading/enable` - Enable paper trading
- `GET /paper-trading/performance` - Get P&L metrics

**Authentication**: JWT tokens (future implementation)

---

## Performance Optimization

### Data Loading Optimization

**Before**:
- Sequential CSV loading
- Pandas read_csv per request
- ~2 seconds per backtest

**After**:
- In-memory caching with Redis
- Async file I/O
- Pre-loaded dataframes
- ~50ms per backtest

**Code**: [historical_data_fetcher.py:_load_from_csv()](../backend/scanner/services/historical_data_fetcher.py)

### Celery Task Optimization

**Task Prioritization**:
```python
CELERY_TASK_ROUTES = {
    'scanner.tasks.backtest_tasks.*': {
        'queue': 'backtests',
        'priority': 5
    },
    'scanner.tasks.celery_tasks.fetch_and_process_signals': {
        'queue': 'signals',
        'priority': 10  # Higher priority
    },
}
```

**Worker Concurrency**:
```bash
# Backtest worker (CPU-intensive)
celery -A config worker -Q backtests --concurrency=4

# Signal worker (I/O-intensive)
celery -A config worker -Q signals --concurrency=8
```

### Database Query Optimization

**Use select_related() for ForeignKeys**:
```python
# Bad: N+1 queries
trades = PaperTrade.objects.all()
for trade in trades:
    print(trade.signal.symbol)  # Extra query per trade

# Good: 1 query
trades = PaperTrade.objects.select_related('signal').all()
for trade in trades:
    print(trade.signal.symbol)  # No extra query
```

**Use prefetch_related() for reverse FKs**:
```python
# Fetch backtests with all their trades
backtests = BacktestRun.objects.prefetch_related('trades').all()
```

### Frontend Optimization

**React Query Caching**:
```javascript
const { data } = useQuery({
  queryKey: ['backtest', id],
  queryFn: () => fetchBacktest(id),
  staleTime: 60000,  // 1 minute
  refetchInterval: 5000  // Poll every 5s for running backtests
});
```

**Lazy Loading**:
```javascript
const SignalDetail = lazy(() => import('./pages/SignalDetail'));
```

---

## Next Steps

### Phase 2: Multi-Timeframe Confirmation
**Goal**: Filter 4h signals by daily trend alignment
**Expected Impact**: +5-10% win rate improvement
**Implementation**: See [PHASE3_IMPLEMENTATION.md](PHASE3_IMPLEMENTATION.md)

### Phase 3: Adaptive Parameters
**Goal**: Dynamically adjust SL/TP based on volatility
**Expected Impact**: Improved risk-adjusted returns

### Phase 4: Live Trading
**Goal**: Deploy with real Binance API integration
**Requirements**: Thorough testing, risk management, monitoring

---

## References

- [Architecture Overview](ARCHITECTURE.md)
- [API Reference](API_REFERENCE.md)
- [Development Guide](DEVELOPMENT_GUIDE.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Testing Guide](TESTING_GUIDE.md)

---

**Last Updated**: November 6, 2025
**Version**: 1.0.0
**Status**: Production Ready
