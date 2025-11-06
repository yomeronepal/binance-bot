# 🚀 START HERE - Management Commands Quick Guide

## ✅ Everything is Ready!

All Python scripts have been converted to Django management commands with full documentation.

---

## 🐳 Step 1: Fix Docker (If Not Running)

### Quick Fix:
1. **Quit Docker Desktop** (right-click system tray icon → Quit)
2. **Wait 10 seconds**
3. **Restart Docker Desktop**
4. **Wait until it says "Docker Desktop is running"**

### Still Not Working?
See: [FIX_DOCKER_IO_ERROR.md](FIX_DOCKER_IO_ERROR.md)

---

## 🏃 Step 2: Start Containers

```bash
cd d:\Project\binance-bot
docker-compose up -d
```

**Check status:**
```bash
docker-compose ps
```

**Expected output:**
```
NAME                      STATUS
binance-bot-backend-1     Up
binance-bot-db-1          Up
binance-bot-redis-1       Up
...
```

---

## ✅ Step 3: Test Commands Work

### Windows:
```bash
test_commands.bat
```

### Linux/Mac:
```bash
chmod +x test_commands.sh
./test_commands.sh
```

### Manual Test:
```bash
docker-compose exec backend python manage.py help
```

**You should see these commands:**
- ✅ analyze_trades
- ✅ analyze_performance
- ✅ clean_database
- ✅ create_paper_account
- ✅ monitor_backtests

---

## 🎯 Step 4: Start Using!

### Create Paper Account:
```bash
docker-compose exec backend python manage.py create_paper_account --balance 10000
```

### Check Trades:
```bash
docker-compose exec backend python manage.py analyze_trades
```

### Review Performance:
```bash
docker-compose exec backend python manage.py analyze_performance
```

---

## 📚 Full Documentation

| File | What It Contains |
|------|------------------|
| [QUICK_COMMANDS.md](QUICK_COMMANDS.md) | Quick reference card |
| [docs/MANAGEMENT_COMMANDS.md](docs/MANAGEMENT_COMMANDS.md) | Complete guide (800+ lines) |
| [FINAL_STATUS_UPDATE.md](FINAL_STATUS_UPDATE.md) | What was completed |
| [FIX_DOCKER_IO_ERROR.md](FIX_DOCKER_IO_ERROR.md) | Docker troubleshooting |

---

## ❓ Need Help?

**Get command help:**
```bash
docker-compose exec backend python manage.py <command> --help
```

**Example:**
```bash
docker-compose exec backend python manage.py analyze_trades --help
```

---

## 🎉 You're All Set!

All 5 management commands are ready:
1. ✅ analyze_trades - Trade diagnostics
2. ✅ analyze_performance - Performance review
3. ✅ clean_database - Database cleanup
4. ✅ create_paper_account - Account setup
5. ✅ monitor_backtests - Backtest monitoring

**Just fix Docker and you're ready to go!** 🚀
