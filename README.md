# RevX Trading Bot

AI-powered cryptocurrency trading bot for Binance Futures with auto-optimized trading windows, real-time sentiment analysis, and intelligent risk management.

## What It Does

RevX scans the crypto market 24/7, generates trading signals using technical indicators, and automatically executes futures trades on Binance — but only during time windows where historical win rate exceeds 60%. The bot learns from its own performance data to continuously optimize when and how it trades.

### Key Capabilities

- **Auto-Optimized Golden Windows** — ML-driven analysis of 3500+ paper trades identifies the exact hours and days with highest win rates. The bot only trades during these windows.
- **Fear & Greed Filter** — Uses CoinMarketCap's Fear & Greed Index to align trade direction with market sentiment. Blocks counter-trend trades automatically.
- **Batch Order Execution** — Places entry + stop loss + take profit in a single Binance API call with 3-level fallback to ensure SL/TP are always set.
- **Paper Trading Validation** — Every signal is automatically paper traded with $100 position size to build a performance dataset before risking real capital.
- **Real-Time Dashboard** — Live P/L tracking, Fear & Greed widget, trading session status, and historical performance analytics.

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│   React UI  │◄──►│  Django API  │◄──►│  PostgreSQL DB  │
│  (Vite PWA) │    │  (DRF + WS)  │    │                 │
└─────────────┘    └──────┬───────┘    └─────────────────┘
                          │
                   ┌──────┴───────┐
                   │ Celery Workers│
                   │  + Beat       │
                   └──────┬───────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
        ┌─────┴─────┐ ┌──┴───┐ ┌────┴────┐
        │  Binance   │ │Redis │ │ Signal  │
        │ Futures API│ │Cache │ │ Engine  │
        └───────────┘ └──────┘ └─────────┘
```

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, TailwindCSS, Lucide Icons |
| Backend | Django 4.2, Django REST Framework, Channels (WebSocket) |
| Task Queue | Celery 5.3, Redis, Celery Beat |
| Database | PostgreSQL 15 |
| Trading | Binance Futures API (aiohttp async) |
| ML/Analysis | scikit-learn, pandas, numpy |
| Deployment | Docker Compose |

## Project Structure

```
revx/
├── backend/
│   ├── config/                         # Django settings, Celery config
│   ├── scanner/
│   │   ├── services/                   # Binance client, Fibonacci watcher
│   │   ├── strategies/                 # Signal engine, signal generator
│   │   └── tasks/                      # Multi-timeframe scanners, golden window trader
│   ├── signals/
│   │   ├── models.py                   # Signal, PaperTrade, TradingSession, PaperAccount
│   │   ├── models_futures.py           # FuturesTrade, FuturesTradingSettings
│   │   ├── services/
│   │   │   ├── futures_trader.py       # Binance futures execution (batch + fallback)
│   │   │   ├── paper_trader.py         # Paper trading simulation
│   │   │   ├── fear_greed.py           # CoinMarketCap Fear & Greed Index
│   │   │   ├── golden_window_analyzer.py # Auto-optimizer for trading windows
│   │   │   └── auto_trader.py          # Auto-trading for paper accounts
│   │   ├── signals_handlers.py         # Django signal handlers (trade execution)
│   │   ├── tasks_golden_window.py      # Celery task for window optimization
│   │   ├── views_public_paper_trading.py # Public paper trading API
│   │   ├── views_futures.py            # Futures trading + F&G API
│   │   └── management/commands/
│   │       ├── optimize_golden_windows.py  # Manual window optimization
│   │       ├── test_futures_order.py       # Test order placement on Binance
│   │       ├── remove_duplicate_trades.py  # Clean duplicate paper trades
│   │       └── mark_golden_window.py       # Backfill GW flags on trades
│   └── api/urls.py                     # All API routes
├── client/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── dashboard/Dashboard.jsx     # Main dashboard with F&G widget
│   │   │   ├── BotPerformance.jsx          # Paper trading analytics
│   │   │   ├── FuturesPerformance.jsx      # Real futures P/L tracking
│   │   │   ├── TradingSessions.jsx         # Golden window viewer
│   │   │   └── Futures.jsx                 # Futures signal cards
│   │   └── components/common/
│   │       ├── FearGreedWidget.jsx         # F&G index display
│   │       └── TradingSessionStatus.jsx    # Session status component
│   └── .env                            # VITE_API_URL, VITE_WS_URL
├── docker-compose.yml
└── README.md
```

## Features

### Signal Generation
- Multi-timeframe scanning: 15m, 1h, 4h, 1D
- RSI-based mean reversion with 10-indicator weighted scoring
- Confidence threshold filtering (default 73%)
- Spot and Futures market support
- WebSocket real-time signal broadcasting

### Futures Trading Engine
- Batch order placement (entry + SL + TP in single API call)
- 3-level SL/TP fallback: algo order → quantity+reduceOnly → closePosition
- Mandatory stop loss — position auto-closed if SL cannot be placed
- Duplicate trade prevention with signal-level locking
- FuturesTrade record created only after Binance confirms execution

### Golden Window Optimizer
- Analyzes all closed paper trades by NPT hour and weekday
- Identifies contiguous hour blocks with >= 60% win rate
- GW1: All-day windows (e.g., 17:00-18:00 NPT — 76% WR)
- GW2: Day-specific windows (e.g., Sun 09:00-10:00 — 95% WR)
- Auto-updates TradingSession records monthly via Celery Beat
- `update_or_create` prevents duplicate sessions

### Fear & Greed Index
- Source: CoinMarketCap (matches Binance app display)
- Cached 15 minutes to avoid rate limits
- Configurable thresholds: F&G <= 30 = SHORT only, F&G >= 60 = LONG only
- Toggle on/off from Django Admin without restart
- Live widget on Dashboard and Futures Performance pages

### Paper Trading
- Every signal auto-creates a $100 paper trade
- Real-time P/L with live Binance prices
- GW1/GW2 AI filters for performance analysis
- Exact NPT hour/weekday matching for accurate win rate calculation
- Duplicate detection and cleanup tools

### Performance Dashboard
- Live P/L (realized + unrealized)
- Win rate, max drawdown, average duration
- Filter by: direction, golden window, hour, weekday, month, year
- GW1 AI / GW2 AI filters show performance within optimized windows
- Pagination with 20 trades per page

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Binance API key with Futures trading enabled

### Setup

```bash
git clone <repo-url>
cd revx

docker-compose up -d --build

docker exec revx-backend python manage.py migrate
docker exec revx-backend python manage.py createsuperuser
```

### Configure Trading

1. Go to Django Admin → **Futures Trading Settings**
2. Set:
   - `is_enabled`: True
   - `trade_amount`: $7.50 (for $30 account)
   - `leverage`: 5
   - `max_concurrent_trades`: 1
   - `fear_greed_enabled`: True
   - `allowed_symbols`: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]

3. Run the golden window optimizer:
```bash
docker exec revx-backend python manage.py optimize_golden_windows
```

### Access
- Dashboard: http://localhost:3000
- API: http://localhost:8000/api
- Admin: http://localhost:8000/admin
- Trading Sessions: http://localhost:3000/trading-sessions
- Bot Performance: http://localhost:3000/bot-performance
- Futures Performance: http://localhost:3000/futures-performance

## API Endpoints

### Public (No Auth)
```
GET  /api/public/paper-trading/              # Paper trades (paginated)
GET  /api/public/paper-trading/summary/      # Performance metrics
GET  /api/public/paper-trading/open-positions/ # Live open positions
GET  /api/futures/fear-greed/                # Fear & Greed Index
GET  /api/trading-sessions/                  # Active trading windows
```

### Authenticated
```
GET  /api/signals/                           # Trading signals
GET  /api/futures/summary/                   # Futures P/L summary
GET  /api/futures/positions/                 # Open futures positions
GET  /api/futures/trades/                    # Futures trade history
POST /api/futures/trades/{id}/close/         # Close a futures trade
GET/PATCH /api/futures/settings/             # Trading settings
POST /api/futures/toggle/                    # Enable/disable trading
```

### Backtesting
```
POST /api/backtest/                          # Create backtest run
GET  /api/backtest/{id}/                     # Get backtest results
GET  /api/strategy/performance/v2/           # Strategy analytics
```

## Management Commands

```bash
docker exec revx-backend python manage.py optimize_golden_windows          # Find best trading windows
docker exec revx-backend python manage.py optimize_golden_windows --dry-run # Preview only
docker exec revx-backend python manage.py test_futures_order               # Dry run order test
docker exec revx-backend python manage.py test_futures_order --execute     # Place real $5 test trade
docker exec revx-backend python manage.py remove_duplicate_trades          # Find duplicates
docker exec revx-backend python manage.py remove_duplicate_trades --execute # Delete duplicates
docker exec revx-backend python manage.py mark_golden_window               # Backfill GW flags
```

## Celery Tasks

| Task | Schedule | Purpose |
|---|---|---|
| Multi-timeframe scan (1h) | Every hour | Generate spot + futures signals |
| Paper trade check | Every 30s | Check SL/TP on open paper trades |
| Futures sync | Every 30s | Sync positions with Binance |
| Golden window trader | Every 30s | Auto-trade during GW sessions |
| Golden window optimizer | 1st of month, 3AM UTC | Re-analyze and update windows |
| Fibonacci pullback monitor | Every 30s | Track fib retracement entries |

## Trading Strategy

### Signal Generation
- RSI 23-33 (LONG) or 67-77 (SHORT)
- ADX >= 22 for trend strength
- 10-indicator weighted scoring with 73% confidence threshold
- Multi-timeframe: 15m, 1h, 4h, 1D

### Futures Execution
- SL: 2.5% from entry
- TP: 6% from entry (1:2.4 R/R)
- Isolated margin, configurable leverage (default 5x)
- Only during auto-optimized golden windows (60%+ historical win rate)
- Fear & Greed directional filter

### Risk Management
- Mandatory stop loss on every trade
- Position auto-closed if SL placement fails
- Max 1 concurrent trade per symbol+direction
- Fear & Greed blocks counter-trend trades
- Dynamic trailing stop (configurable tiers)
- Cut loser feature (close recovering losers at breakeven)

## Environment Variables

### Backend (.env)
```
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_secret
DATABASE_URL=postgres://user:pass@db:5432/revx
REDIS_URL=redis://redis:6379/0
DJANGO_SECRET_KEY=your_secret_key
```

### Frontend (.env)
```
VITE_API_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000/ws/signals/
```

## Performance

### Current Results (Paper Trading, 3500+ trades)
- **GW1 17:00-18:00 NPT**: 76.2% win rate (185 trades)
- **GW1 21:00-23:00 NPT**: 70.6% win rate (612 trades)
- **GW2 Sun 09:00-10:00**: 94.7% win rate (19 trades)
- **GW2 Wed 21:00-24:00**: 87.7% win rate (130 trades)
- **Overall bot P/L**: +$3,515 on paper trades

### Conservative Estimate ($30 account, 5x leverage)
- ~10 trades/month during golden windows
- 70% win rate, $2.25 avg win, $0.94 avg loss
- Expected: +$12.93/month (~43% ROI)

## License

MIT
