# RevX Trading Bot

Automated cryptocurrency trading bot for Binance with Django backend, Celery task queue, and RSI-based mean reversion strategy.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Git

### Setup

```bash
git clone <repo-url>
cd revx

cd docker
docker-compose up -d

docker exec revx_web python manage.py migrate
docker exec revx_web python manage.py createsuperuser
```

### Access
- Web App: http://localhost:3000
- API: http://localhost:8000/api
- Admin: http://localhost:8000/admin

## Project Structure

```
revx/
├── backend/                    # Django application
│   ├── scanner/
│   │   ├── services/           # Business logic
│   │   ├── strategies/         # Trading strategies
│   │   └── tasks/              # Celery tasks
│   └── signals/                # Models, views, serializers
├── client/                     # React frontend
├── docker/                     # Docker configuration
└── scripts/                    # Utility scripts
```

## Features

- Multi-timeframe scanning (15m, 1h, 4h, 1d)
- Spot and Futures market support
- Paper trading mode
- Backtesting engine
- WebSocket real-time updates
- Signal notifications (Discord, Telegram)

## Trading Strategy

RSI-based mean reversion with trend confirmation:

- Entry: RSI 23-33 (LONG), 67-77 (SHORT)
- ADX > 22 for trend strength
- Confidence threshold: 73%
- Stop Loss: 1.5x ATR
- Take Profit: 5.25x ATR (1:3.5 R/R)

## API Endpoints

```
POST /api/backtest/           # Create backtest
GET  /api/backtest/{id}/      # Get results
GET  /api/signals/            # List signals
GET  /api/paper-trading/      # Paper trading stats
```

## Docker Commands

```bash
docker-compose up -d          # Start services
docker-compose down           # Stop services
docker-compose logs -f        # View logs
docker exec revx_web python manage.py shell  # Django shell
```

## Environment Variables

Copy `.env.example` to `.env` in both `backend/` and `client/` directories.

Key variables:
- `BINANCE_API_KEY` - Binance API key
- `BINANCE_SECRET_KEY` - Binance secret
- `DISCORD_WEBHOOK_URL` - Discord notifications
- `TELEGRAM_BOT_TOKEN` - Telegram notifications

## License

MIT
