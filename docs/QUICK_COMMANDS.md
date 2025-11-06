# Quick Command Reference

## All Django Management Commands

### Analysis Commands

```bash
# Analyze paper trades (TP/SL diagnostics)
python manage.py analyze_trades
python manage.py analyze_trades --status CLOSED --limit 20

# Comprehensive performance analysis
python manage.py analyze_performance
```

### Setup Commands

```bash
# Create paper trading account
python manage.py create_paper_account
python manage.py create_paper_account --balance 10000 --max-trades 10

# Clean database
python manage.py clean_database --simple
python manage.py clean_database --yes --keep-accounts
```

### Monitoring Commands

```bash
# Monitor backtests
python manage.py monitor_backtests 1-10
python manage.py monitor_backtests 1 2 3 --no-wait
```

## Docker Usage

**Always run inside Docker container:**

```bash
docker-compose exec backend python manage.py <command>
```

### Examples

```bash
# Analyze trades
docker-compose exec backend python manage.py analyze_trades --status CLOSED

# Create account
docker-compose exec backend python manage.py create_paper_account --balance 5000

# Clean database
docker-compose exec backend python manage.py clean_database --simple

# Monitor backtests
docker-compose exec backend python manage.py monitor_backtests 1-5
```

## Help System

```bash
# Get list of all commands
docker-compose exec backend python manage.py help

# Get help for specific command
docker-compose exec backend python manage.py <command> --help

# Examples
docker-compose exec backend python manage.py help analyze_trades
docker-compose exec backend python manage.py analyze_performance --help
```

## Common Workflows

### Initial Setup
```bash
docker-compose exec backend python manage.py create_paper_account --balance 10000
```

### Daily Monitoring
```bash
docker-compose exec backend python manage.py analyze_trades
```

### Weekly Review
```bash
docker-compose exec backend python manage.py analyze_performance
```

### Fresh Start
```bash
docker-compose exec backend python manage.py clean_database --simple
docker-compose restart backend celery-worker
```

## Full Documentation

See [docs/MANAGEMENT_COMMANDS.md](docs/MANAGEMENT_COMMANDS.md) for complete reference.
