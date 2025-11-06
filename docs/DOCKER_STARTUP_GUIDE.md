# Docker Startup & Command Testing Guide

## Current Issue

Docker containers are not running due to an image error. Here's how to fix and verify the management commands.

## Fix Docker Issues

### Option 1: Quick Fix - Restart Docker Desktop

1. **Restart Docker Desktop**
   - Close Docker Desktop completely
   - Reopen Docker Desktop
   - Wait for it to fully start

2. **Clean Docker cache**
   ```bash
   docker system prune -a
   ```
   ⚠️ Warning: This removes all unused images

3. **Rebuild containers**
   ```bash
   cd d:\Project\binance-bot
   docker-compose build --no-cache
   docker-compose up -d
   ```

### Option 2: Selective Rebuild

```bash
cd d:\Project\binance-bot

# Rebuild only backend
docker-compose build --no-cache backend

# Start all services
docker-compose up -d

# Check status
docker-compose ps
```

### Option 3: Complete Reset

```bash
cd d:\Project\binance-bot

# Stop everything
docker-compose down

# Remove volumes (⚠️ This deletes database data!)
docker-compose down -v

# Rebuild from scratch
docker-compose build --no-cache

# Start fresh
docker-compose up -d
```

## Verify Containers Are Running

```bash
# Check container status
docker-compose ps

# Expected output:
# NAME                    STATUS    PORTS
# binance-bot-backend-1   Up        0.0.0.0:8000->8000/tcp
# binance-bot-db-1        Up        5432/tcp
# binance-bot-redis-1     Up        6379/tcp
# ...
```

## Test Management Commands

### Quick Test (Windows)

Run the provided test script:
```bash
test_commands.bat
```

### Quick Test (Linux/Mac)

```bash
chmod +x test_commands.sh
./test_commands.sh
```

### Manual Testing

Once Docker is running, test each command:

```bash
# 1. List all available commands
docker-compose exec backend python manage.py help

# 2. Test each command's help
docker-compose exec backend python manage.py analyze_trades --help
docker-compose exec backend python manage.py analyze_performance --help
docker-compose exec backend python manage.py clean_database --help
docker-compose exec backend python manage.py create_paper_account --help
docker-compose exec backend python manage.py monitor_backtests --help

# 3. Test actual execution
docker-compose exec backend python manage.py create_paper_account --balance 1000
docker-compose exec backend python manage.py analyze_trades
```

## Troubleshooting

### Issue: "Command not found"

**Solution 1: Check file exists**
```bash
docker-compose exec backend ls -la /app/signals/management/commands/
```

Expected files:
- analyze_trades.py
- analyze_performance.py
- clean_database.py
- create_paper_account.py
- monitor_backtests.py

**Solution 2: Restart Django**
```bash
docker-compose restart backend
```

### Issue: "ImportError" when running commands

**Solution 1: Run migrations**
```bash
docker-compose exec backend python manage.py migrate
```

**Solution 2: Check Django can import models**
```bash
docker-compose exec backend python manage.py shell -c "from signals.models import PaperTrade; print('OK')"
```

### Issue: "No module named 'signals'"

**Solution: Check working directory**
```bash
docker-compose exec backend pwd
# Should output: /app

docker-compose exec backend ls
# Should show: backend, client, docs, etc.
```

### Issue: Docker build fails

**Solution 1: Check Docker Desktop is running**
- Open Docker Desktop app
- Ensure Docker Engine is started

**Solution 2: Clear Docker cache**
```bash
docker system prune -a -f
```

**Solution 3: Check disk space**
```bash
docker system df
```

## Verification Checklist

Once Docker is running, verify everything works:

- [ ] Docker containers are running (`docker-compose ps`)
- [ ] Backend is accessible (`docker-compose logs backend`)
- [ ] Commands are registered (`docker-compose exec backend python manage.py help`)
- [ ] analyze_trades works (`docker-compose exec backend python manage.py analyze_trades --help`)
- [ ] analyze_performance works (`docker-compose exec backend python manage.py analyze_performance --help`)
- [ ] clean_database works (`docker-compose exec backend python manage.py clean_database --help`)
- [ ] create_paper_account works (`docker-compose exec backend python manage.py create_paper_account --help`)
- [ ] monitor_backtests works (`docker-compose exec backend python manage.py monitor_backtests --help`)

## Quick Start Commands

After Docker is running:

```bash
# Create paper account
docker-compose exec backend python manage.py create_paper_account --balance 10000

# Analyze trades (once you have some)
docker-compose exec backend python manage.py analyze_trades

# View performance
docker-compose exec backend python manage.py analyze_performance

# Clean database (simple mode - safe)
docker-compose exec backend python manage.py clean_database --simple
```

## Next Steps After Docker Starts

1. **Create paper account**
   ```bash
   docker-compose exec backend python manage.py create_paper_account --balance 10000
   ```

2. **Wait for signals to generate** (automatic via scanner)

3. **Monitor trades**
   ```bash
   docker-compose exec backend python manage.py analyze_trades
   ```

4. **After 50+ closed trades, run performance analysis**
   ```bash
   docker-compose exec backend python manage.py analyze_performance
   ```

## Useful Docker Commands

```bash
# View logs
docker-compose logs -f backend

# Check backend health
docker-compose exec backend python manage.py check

# Access Django shell
docker-compose exec backend python manage.py shell

# Run migrations
docker-compose exec backend python manage.py migrate

# List all management commands
docker-compose exec backend python manage.py help

# Restart specific service
docker-compose restart backend

# Stop all
docker-compose down

# Start all
docker-compose up -d
```

## Files Created

All management commands are in:
```
backend/signals/management/commands/
├── analyze_trades.py
├── analyze_performance.py
├── clean_database.py
├── create_paper_account.py
└── monitor_backtests.py
```

## Documentation

- **Quick Reference**: [QUICK_COMMANDS.md](QUICK_COMMANDS.md)
- **Full Documentation**: [docs/MANAGEMENT_COMMANDS.md](docs/MANAGEMENT_COMMANDS.md)
- **Conversion Summary**: [docs/SCRIPT_TO_COMMAND_CONVERSION.md](docs/SCRIPT_TO_COMMAND_CONVERSION.md)
- **Analyze Trades Guide**: [docs/ANALYZE_TRADES_COMMAND.md](docs/ANALYZE_TRADES_COMMAND.md)

## Support

If issues persist:
1. Check Docker Desktop is running
2. Try complete rebuild (Option 3 above)
3. Check logs: `docker-compose logs backend`
4. Verify Python environment in container
5. Check [docs/MANAGEMENT_COMMANDS.md](docs/MANAGEMENT_COMMANDS.md) troubleshooting section
