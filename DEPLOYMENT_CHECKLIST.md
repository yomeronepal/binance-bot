# 🚀 Deployment Checklist - Optimization Fixes

**Date**: November 8, 2025
**Fixes**: 9 Critical/High Priority Issues
**Status**: ✅ Ready to Deploy

---

## ⚠️ REQUIRED STEPS (Do Not Skip!)

### 1. Generate SECRET_KEY (Production Only)
```bash
# Generate a secure secret key
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# Copy output and add to .env file
echo "SECRET_KEY=<paste_generated_key_here>" >> .env
```

### 2. Apply Database Migration
```bash
# Apply new performance indexes
docker exec binancebot_web python manage.py migrate signals

# Expected output:
# Running migrations:
#   Applying signals.0015_add_papertrade_performance_indexes... OK
```

### 3. Restart Services
```bash
# Full restart to apply all fixes
docker-compose down
docker-compose up -d --build

# Or using shortcuts
make docker-restart  # Linux/Mac
run.bat docker-restart  # Windows
```

---

## ✅ POST-DEPLOYMENT VERIFICATION

### 1. Check Services Started Successfully
```bash
docker-compose ps

# All services should show "Up"
```

### 2. Verify No Startup Errors
```bash
docker-compose logs -f backend celery_worker

# Look for:
# ✅ "Celery worker ready"
# ✅ "Backend server started"
# ❌ Should NOT see SECRET_KEY error (if production)
```

### 3. Test Configuration Validation
```bash
docker exec binancebot_web python backend/scanner/config/user_config.py

# Should see:
# ✅ ALL CONFIGURATIONS VALID
```

### 4. Test Commodity API (Soybean Fix)
```bash
docker exec binancebot_celery python -c "
from scanner.tasks.forex_scanner import COMMODITY_SYMBOLS
print('Soybean symbol:', 'SOYBEANSUSD' in COMMODITY_SYMBOLS)
"

# Should print: Soybean symbol: True
```

---

## 📊 MONITORING (First 48 Hours)

### 1. Watch Memory Usage
```bash
# Should be stable ~200-300MB
docker stats binancebot_celery

# Before fix: Grew 10-20MB/hour, crashed at 2GB
# After fix: Stable memory usage
```

### 2. Monitor Celery Tasks
```bash
docker exec binancebot_celery celery -A config inspect active

# Should show active tasks processing
```

### 3. Check Database Performance
```bash
# Test admin panel responsiveness
# Open: http://localhost:8000/admin/signals/papertrade/
# Should load in <1 second even with thousands of records
```

### 4. Verify Rate Limiting
```bash
docker-compose logs -f celery_worker | grep "Rate limit"

# Should NOT see frequent rate limit warnings
```

---

## 🎯 SUCCESS CRITERIA

- ✅ All Docker containers running
- ✅ No SECRET_KEY error in production
- ✅ Configuration validation passes
- ✅ Soybean symbol recognized
- ✅ Memory usage stable over 24+ hours
- ✅ Admin queries load in <1 second
- ✅ No rate limit errors
- ✅ Celery tasks processing successfully

---

## 🐛 TROUBLESHOOTING

### Issue: "SECRET_KEY must be set" Error (Production)
**Solution**: Set SECRET_KEY environment variable (see step 1)

### Issue: Migration Already Applied
**Solution**: Normal! Django skips already-applied migrations
```bash
docker exec binancebot_web python manage.py showmigrations signals
# Should show [X] next to 0015_add_papertrade_performance_indexes
```

### Issue: Celery Worker Won't Start
**Solution**: Check logs for specific error
```bash
docker-compose logs celery_worker
```

### Issue: Memory Still Growing
**Solution**: Verify fixes were applied
```bash
# Check if asyncio.run() is being used
docker exec binancebot_web grep -n "asyncio.run" backend/scanner/tasks/celery_tasks.py
# Should show line 44

docker exec binancebot_web grep -n "asyncio.run" backend/scanner/tasks/backtest_tasks.py
# Should show line 44
```

---

## 📈 PERFORMANCE EXPECTATIONS

After deployment, you should see:

| Metric | Target | Check |
|--------|--------|-------|
| Celery worker uptime | >7 days | `docker ps` |
| Memory usage | <300MB stable | `docker stats` |
| Admin query time | <500ms | Browser devtools |
| Paper trading loop | <100ms | Celery logs |
| Soybean data | Available | Forex scanner logs |

---

## 🔄 ROLLBACK PROCEDURE (If Needed)

If issues occur, rollback:

```bash
# 1. Stop services
docker-compose down

# 2. Revert changes
git stash

# 3. Restart
docker-compose up -d

# 4. Report issue with logs
docker-compose logs --tail=100 > error_logs.txt
```

---

## 📝 WHAT WAS FIXED

1. ✅ **Critical Typo**: SOYBEANUSД → SOYBEANSUSD
2. ✅ **Memory Leaks**: Event loop cleanup in 3 files
3. ✅ **N+1 Queries**: Paper trading optimization
4. ✅ **Security**: SECRET_KEY validation
5. ✅ **Exception Handling**: Bare except replaced
6. ✅ **Database Indexes**: 3 new composite indexes
7. ✅ **Rate Limiter**: Thread-safe with asyncio.Lock
8. ✅ **Logging**: Print statements replaced

**Full details**: See [docs/OPTIMIZATION_FIXES_NOV8.md](docs/OPTIMIZATION_FIXES_NOV8.md)

---

## 📞 SUPPORT

For issues:
1. Check logs: `docker-compose logs -f`
2. Review: [docs/OPTIMIZATION_FIXES_NOV8.md](docs/OPTIMIZATION_FIXES_NOV8.md)
3. Consult: [CLAUDE.md](CLAUDE.md) for troubleshooting

---

**Last Updated**: November 8, 2025
**Estimated Deployment Time**: 5-10 minutes
**Downtime Required**: 2-3 minutes (during restart)
