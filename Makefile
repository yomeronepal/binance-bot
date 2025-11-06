# Binance Trading Bot - Makefile
# Easy command execution for backtesting and optimization

.PHONY: help setup download-data test-short test-long optimize clean docker-restart

# Default target
help:
	@echo "========================================"
	@echo "Binance Trading Bot - Available Commands"
	@echo "========================================"
	@echo ""
	@echo "Setup & Data:"
	@echo "  make setup              - Initial setup and verify Docker containers"
	@echo "  make download-short     - Download 3-month historical data"
	@echo "  make download-long      - Download 11-month historical data (recommended)"
	@echo "  make download-all       - Download all timeframes (5m, 15m, 1h, 4h, 1d)"
	@echo ""
	@echo "Testing & Optimization:"
	@echo "  make test-short         - Run backtest on 3-month period"
	@echo "  make test-long          - Run backtest on 11-month period"
	@echo "  make optimize-params    - Run parameter optimization (best config)"
	@echo "  make test-all-symbols   - Test OPT6 on all symbols (BTC, ETH, SOL, DOGE)"
	@echo ""
	@echo "Docker Management:"
	@echo "  make docker-restart     - Restart all Docker containers"
	@echo "  make docker-logs        - Show Docker logs"
	@echo "  make docker-status      - Check Docker container status"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean-data         - Remove downloaded backtest data"
	@echo "  make clean-results      - Clean old backtest results from DB"
	@echo "  make clean-all          - Clean data + results"
	@echo ""
	@echo "Advanced:"
	@echo "  make shell              - Open shell in backend container"
	@echo "  make celery-shell       - Open shell in Celery worker container"
	@echo ""

# === SETUP ===
setup:
	@echo "🔧 Checking Docker containers..."
	@docker ps | grep binance-bot || (echo "❌ Containers not running. Start them with: docker-compose up -d" && exit 1)
	@echo "✅ Docker containers running"
	@echo ""
	@echo "📦 Checking Python dependencies..."
	@docker exec binance-bot-backend pip list | grep -E "pandas|aiohttp|requests" > /dev/null || echo "⚠️  Some dependencies might be missing"
	@echo "✅ Setup complete"

# === DATA DOWNLOAD ===
download-short:
	@echo "📥 Downloading 3-month historical data (Aug-Nov 2024)..."
	@docker exec binance-bot-backend python scripts/data/download_data_fast.py
	@docker exec binance-bot-backend bash -c "cp -r backtest_data/* /app/backtest_data/ 2>/dev/null || true"
	@echo "✅ Short period data downloaded"

download-long:
	@echo "📥 Downloading 11-month historical data (Jan-Nov 2024)..."
	@docker exec binance-bot-backend python scripts/data/download_long_period.py
	@docker exec binance-bot-backend bash -c "cp -r backtest_data_extended/* backtest_data/"
	@echo "✅ Long period data downloaded"

download-all:
	@echo "📥 Downloading all timeframes for all symbols..."
	@echo "   This will download: 5m, 15m, 1h, 4h, 1d"
	@echo "   Symbols: BTCUSDT, ETHUSDT, SOLUSDT, DOGEUSDT"
	@echo "   Period: Jan 2024 - Nov 2025 (11 months)"
	@echo ""
	@docker exec binance-bot-backend python scripts/data/download_long_period.py
	@echo "✅ All data downloaded (~1.1M candles)"

# === TESTING & OPTIMIZATION ===
test-short:
	@echo "🧪 Running backtest on 3-month period..."
	@docker exec binance-bot-backend python scripts/testing/test_extended_period.py | grep -A 100 "3 Months"

test-long:
	@echo "🧪 Running backtest on 11-month extended period..."
	@docker exec binance-bot-backend python scripts/testing/test_extended_period.py

optimize-params:
	@echo "⚙️  Running parameter optimization..."
	@echo "   Testing 8 different configurations on 4h BTCUSDT"
	@docker exec binance-bot-backend python scripts/optimization/optimize_parameters_final.py

test-all-symbols:
	@echo "📊 Testing OPT6 configuration on all symbols..."
	@docker exec binance-bot-backend python scripts/testing/test_extended_period.py

# === DOCKER MANAGEMENT ===
docker-restart:
	@echo "🔄 Restarting Docker containers..."
	@docker restart binance-bot-backend binance-bot-celery-worker binance-bot-db binance-bot-redis
	@sleep 3
	@echo "✅ Containers restarted"

docker-logs:
	@echo "📋 Docker logs (Ctrl+C to exit)..."
	@docker-compose logs -f --tail=50

docker-status:
	@echo "📊 Docker container status:"
	@docker ps --filter "name=binance-bot" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# === CLEANUP ===
clean-data:
	@echo "🗑️  Removing backtest data..."
	@docker exec binance-bot-backend bash -c "rm -rf backtest_data backtest_data_extended"
	@echo "✅ Data cleaned"

clean-results:
	@echo "🗑️  Cleaning old backtest results..."
	@docker exec binance-bot-backend python manage.py shell -c "from signals.models import BacktestRun; BacktestRun.objects.filter(status='COMPLETED').delete(); print('Deleted old results')"
	@echo "✅ Results cleaned"

clean-all: clean-data clean-results
	@echo "✅ All cleaned"

# === ADVANCED ===
shell:
	@echo "🐚 Opening shell in backend container..."
	@docker exec -it binance-bot-backend bash

celery-shell:
	@echo "🐚 Opening shell in Celery worker container..."
	@docker exec -it binance-bot-celery-worker bash

# === QUICK ACTIONS (Most Common) ===
# Run optimization from scratch
quick-test: docker-restart download-long test-long
	@echo "✅ Complete test finished!"

# === INTERNAL TARGETS ===
.SILENT: help
