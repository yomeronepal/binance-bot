# Binance Trading Bot - Full Stack Application

Complete trading bot platform with Django REST API backend and React frontend, fully containerized with Docker.

[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)](https://github.com/yourusername/binance-bot)
[![Status](https://img.shields.io/badge/status-production--ready-green.svg)](https://github.com/yourusername/binance-bot)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 🚀 Quick Start

### Prerequisites
- Docker Desktop or Docker Engine + Docker Compose (v2.0+)
- 8GB RAM minimum (16GB recommended)
- 10GB free disk space

### Start the Bot (Easiest Method)

**Windows:**
```cmd
cd d:\Project\binance-bot
start.bat
```

**Linux/Mac:**
```bash
cd /path/to/binance-bot
chmod +x start.sh
./start.sh
```

**Access the application:**
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000/api
- **Admin Panel**: http://localhost:8000/admin
- **Flower (Celery Monitor)**: http://localhost:5555

## ✨ Features

### Signal Generation ✅
- **966+ Coins Scanned** - All USDT pairs on Binance spot & futures
- **Real-time Detection** - Signals updated every 5 minutes
- **Multi-timeframe Analysis** - 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
- **8-Point Confidence Scoring** - RSI, MACD, EMA, ATR, ADX, BB, HA
- **Trading Type Classification** - Scalping (⚡), Day (📊), Swing (📈)
- **Dynamic Risk-Reward Ratios** - Optimized by trading type (1.2-3.0)

### Paper Trading ✅
- **Simulated Trading** - No real money at risk
- **Auto Entry/Exit** - SL/TP monitoring
- **Performance Metrics** - Win rate, P/L, duration
- **Real-time Updates** - WebSocket integration
- **Public Dashboard** - See your trades live
- See [docs/PAPER_TRADING_IMPLEMENTATION.md](docs/PAPER_TRADING_IMPLEMENTATION.md)

### Backtesting & Strategy Optimization ✅
- **Historical Testing** - Test strategies on real market data
- **Volatility-Aware Configs** - Auto-adjust parameters by coin type
- **Multiple Optimization Methods** - Walk-forward, Monte Carlo, ML tuning
- **Strategy Dashboard** - Visual performance analytics
- **Configuration Comparison** - Find optimal parameters
- See [docs/PHASE5_FRONTEND_DASHBOARD_COMPLETE.md](docs/PHASE5_FRONTEND_DASHBOARD_COMPLETE.md)

### User Experience ✅
- **Real-time Dashboard** - WebSocket updates
- **Comprehensive Filtering** - Direction, status, timeframe
- **Interactive Charts** - Recharts with TP/SL markers
- **Detailed Signal Pages** - Full analysis + execution guide
- **Dark Mode** - Full theme support
- **Responsive Design** - Mobile, tablet, desktop

## 🏗️ Architecture

```
binance-bot/
├── backend/              # Django REST API
│   ├── api/              # REST endpoints
│   ├── signals/          # Trading signals + Paper trading
│   ├── scanner/          # Market scanner + Signal engine
│   ├── users/            # Authentication
│   └── config/           # Settings + Celery
├── client/               # React Frontend
│   ├── src/
│   │   ├── components/   # UI components
│   │   ├── pages/        # Route pages
│   │   ├── store/        # Zustand state
│   │   └── services/     # API services
├── docs/                 # 📚 Complete documentation
└── docker-compose.yml    # Docker orchestration
```

## 🛠️ Tech Stack

**Backend:**
- Django 5.0 + DRF + Channels
- PostgreSQL 15 + Redis 7
- Celery + Flower
- Binance API (async)

**Frontend:**
- React 18 + Vite
- TailwindCSS + Zustand
- React Router v6
- Recharts + date-fns

**DevOps:**
- Docker + Docker Compose
- Nginx (production)

## 📚 Documentation

All documentation is in the [`docs/`](./docs/) folder:

### Getting Started
- **[Quick Start Guide](docs/QUICKSTART.md)** - 5-minute setup
- **[Quick Reference](docs/QUICK_REFERENCE.md)** - Commands & troubleshooting
- **[Docker Deployment](docs/DOCKER_DEPLOYMENT.md)** - Production setup

### Features & Implementations
- **[Feature Overview](docs/FEATURE_COMPLETE_SUMMARY.md)** - All features
- **[Session Summary](docs/SESSION_SUMMARY.md)** - Latest updates
- **[Trading Types](docs/TRADING_TYPES_IMPLEMENTATION.md)** - Scalping/Day/Swing
- **[Risk-Reward System](docs/RISK_REWARD_OPTIMIZATION.md)** - R/R optimization
- **[Paper Trading](docs/PAPER_TRADING_IMPLEMENTATION.md)** - Simulation guide
- **[Auto Trading](docs/AUTO_TRADING_IMPLEMENTATION_COMPLETE.md)** - Automated execution
- **[Scan Coverage](docs/INCREASED_SCAN_COVERAGE.md)** - 966 coins

### Backtesting & Optimization
- **[Backtesting System](docs/BACKTESTING_SYSTEM_COMPLETE.md)** - Full guide
- **[Walk-Forward Optimization](docs/WALK_FORWARD_IMPLEMENTATION_COMPLETE.md)** - Advanced testing
- **[Monte Carlo Simulation](docs/MONTE_CARLO_IMPLEMENTATION_COMPLETE.md)** - Risk analysis
- **[ML Tuning](docs/ML_TUNING_IMPLEMENTATION_COMPLETE.md)** - AI optimization
- **[Strategy Dashboard](docs/PHASE5_FRONTEND_DASHBOARD_COMPLETE.md)** - Visual analytics
- **[Volatility-Aware Strategy](docs/PHASE1_VOLATILITY_AWARE_COMPLETE.md)** - Adaptive configs
- **[Backtest Results Analysis](docs/BACKTEST_RESULTS_ANALYSIS.md)** - Performance review

### Technical
- **[Signal Engine](docs/SIGNAL_ENGINE_INTEGRATION.md)** - How signals work
- **[Celery Setup](docs/CELERY_INTEGRATION_COMPLETE.md)** - Background tasks
- **[Scanner Guide](docs/SCANNER_QUICKSTART.md)** - Market scanning
- **[UI Improvements](docs/UI_IMPROVEMENTS_SUMMARY.md)** - Frontend details

**[📖 Full Documentation Index](docs/README.md)**

## 🐳 Docker Services

| Service | Port | Description |
|---------|------|-------------|
| **frontend** | 5173 | React dev server / Nginx (prod) |
| **backend** | 8000 | Django API + WebSocket |
| **postgres** | 5432 | PostgreSQL database |
| **redis** | 6379 | Cache & message broker |
| **celery-worker** | - | Background task worker |
| **celery-beat** | - | Task scheduler |
| **flower** | 5555 | Celery monitoring |

## 🌐 API Endpoints

### Authentication
- `POST /api/users/register/` - Register
- `POST /api/users/login/` - Login
- `POST /api/users/token/refresh/` - Refresh token

### Signals
- `GET /api/signals/` - List signals (filter by market_type, status, etc.)
- `GET /api/signals/:id/` - Get signal detail
- `GET /api/symbols/` - Get available symbols

### Paper Trading
- `GET /api/paper-trades/` - List paper trades
- `POST /api/paper-trades/create_from_signal/` - Create trade
- `POST /api/paper-trades/:id/close_trade/` - Close trade
- `GET /api/paper-trades/performance/` - Get metrics

### Backtesting
- `GET /api/backtest/` - List backtests
- `POST /api/backtest/` - Create backtest
- `GET /api/backtest/:id/` - Get backtest details
- `GET /api/backtest/:id/trades/` - Get backtest trades
- `GET /api/walkforward/` - Walk-forward optimizations
- `GET /api/montecarlo/` - Monte Carlo simulations
- `GET /api/mltuning/` - ML tuning jobs

### Strategy Performance
- `GET /api/strategy/performance/` - Aggregated performance analytics

### WebSocket
- `ws://localhost:8000/ws/signals/` - Real-time updates

## 🔧 Common Commands

### Docker Operations
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f celery-worker

# Restart services
docker-compose restart backend celery-worker

# Stop everything
docker-compose down

# Full reset (WARNING: deletes data)
docker-compose down -v
```

### Database Operations
```bash
# Run migrations
docker-compose exec backend python manage.py migrate

# Create superuser
docker-compose exec backend python manage.py createsuperuser

# Django shell
docker-compose exec backend python manage.py shell
```

### Celery Tasks
```bash
# Monitor tasks in Flower
# Open http://localhost:5555

# Manual task execution (Django shell)
docker-compose exec backend python manage.py shell
>>> from scanner.tasks.celery_tasks import scan_binance_market
>>> result = scan_binance_market.delay()
>>> result.get(timeout=120)
```

## 📊 Current Performance

- **Coins Scanned:** 966 (436 spot + 530 futures)
- **Scan Interval:** Every 5 minutes
- **Scan Duration:** 30-60 seconds
- **Active Signals:** 200-400 average
- **API Response Time:** < 200ms
- **WebSocket Latency:** < 50ms

## ⚙️ Configuration

### Backend Environment (`.env` in `backend/`)
```env
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=postgres://tradingbot:password@postgres:5432/tradingbot_db
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
BINANCE_API_KEY=your_api_key  # Optional
BINANCE_API_SECRET=your_secret  # Optional
```

### Frontend Environment (`.env` in `client/`)
```env
VITE_API_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000/ws/signals/
```

## 🧪 Testing

### Run Backend Tests
```bash
docker-compose exec backend pytest -v

# Specific tests
docker-compose exec backend pytest scanner/tests/test_signal_engine.py -v
```

### Test Celery Tasks
```bash
# Enter Django shell
docker-compose exec backend python manage.py shell

# Test market scan
>>> from scanner.tasks.celery_tasks import scan_binance_market
>>> result = scan_binance_market.delay()
>>> print(result.get(timeout=120))
```

## 🚦 System Status

**Version:** 4.0.0
**Status:** ✅ Production Ready
**Last Updated:** October 30, 2025

### What's Working ✅
- Signal generation (966 coins)
- Real-time WebSocket updates
- Trading type classification
- Risk-reward optimization
- Paper trading (full stack)
- Auto trading execution
- Backtesting engine
- Walk-forward optimization
- Monte Carlo simulation
- ML parameter tuning
- Volatility-aware strategies
- Strategy performance dashboard
- Comprehensive UI/UX
- Docker deployment
- Celery background tasks

### Coming Soon 🔄
- Email notifications
- Mobile app
- Kubernetes deployment

## 🛣️ Roadmap

### Phase 1: Foundation ✅
- [x] Django backend with JWT auth
- [x] React frontend with routing
- [x] Docker containerization
- [x] WebSocket real-time updates

### Phase 2: Signal Engine ✅
- [x] Binance API integration
- [x] Multi-indicator analysis
- [x] Signal generation & tracking
- [x] Celery background tasks
- [x] Trading type classification
- [x] Risk-reward optimization

### Phase 3: Paper Trading ✅
- [x] Database model & service
- [x] Performance metrics
- [x] Frontend implementation
- [x] WebSocket updates
- [x] Public dashboard

### Phase 4: Backtesting & Optimization ✅
- [x] Backtesting engine
- [x] Walk-forward optimization
- [x] Monte Carlo simulation
- [x] ML-based parameter tuning
- [x] Volatility-aware configurations
- [x] Strategy performance dashboard

### Phase 5: Production Features
- [x] Strategy analytics dashboard
- [ ] Email notifications
- [ ] Mobile app
- [ ] Kubernetes deployment
- [ ] Monitoring & alerting

## 🐛 Troubleshooting

### Port Already in Use
Edit `docker-compose.yml` and change port mappings.

### Database Connection Failed
```bash
docker-compose restart postgres
docker-compose logs postgres
```

### Celery Not Running
```bash
docker-compose restart celery-worker celery-beat
docker-compose logs celery-worker
```

### Frontend Not Loading
```bash
docker-compose logs -f frontend
docker-compose restart frontend
```

### Full System Reset
```bash
docker-compose down -v
docker-compose up -d --build
docker-compose exec backend python manage.py migrate
```

## 🔐 Security Checklist

Before production deployment:

- [ ] Change `SECRET_KEY` to secure random value
- [ ] Set `DEBUG=False`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Use strong database passwords
- [ ] Enable HTTPS/SSL
- [ ] Configure CORS properly
- [ ] Set up firewall rules
- [ ] Enable rate limiting
- [ ] Configure security headers
- [ ] Set up monitoring and logging
- [ ] Secure Binance API keys
- [ ] Enable database backups

## 📖 Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [React Documentation](https://react.dev/)
- [Binance API Documentation](https://binance-docs.github.io/apidocs/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [Docker Documentation](https://docs.docker.com/)

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

[MIT License](LICENSE) - see LICENSE file for details

## 💬 Support

- **Documentation:** Check [docs/](docs/) folder
- **Issues:** Open a GitHub issue
- **Quick Help:** See [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)

## ⭐ Acknowledgments

- Django REST Framework team
- React & Vite teams
- Binance API
- TailwindCSS
- All open source contributors

---

**Built with ❤️ for crypto traders**

[![Star History](https://img.shields.io/github/stars/yourusername/binance-bot?style=social)](https://github.com/yourusername/binance-bot)
