# Paper Trading API - Quick Reference

## 🔐 User-Specific Endpoints (Auth Required)

### GET /api/paper-trades/
List current user's trades
```bash
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/api/paper-trades/
```

### GET /api/paper-trades/performance/
Current user's performance metrics
```bash
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/api/paper-trades/performance/
```

### GET /api/paper-trades/open_positions/
Current user's open positions with real-time prices
```bash
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/api/paper-trades/open_positions/
```

### GET /api/paper-trades/summary/
Current user's comprehensive summary
```bash
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/api/paper-trades/summary/
```

---

## 🌐 Public Endpoints (No Auth Required)

### GET /api/public/paper-trading/
List ALL paper trades (all users)
```bash
curl http://localhost:8000/api/public/paper-trading/
```

### GET /api/public/paper-trading/performance/
System-wide performance metrics
```bash
curl http://localhost:8000/api/public/paper-trading/performance/
```

### GET /api/public/paper-trading/open-positions/
ALL open positions with real-time prices
```bash
curl http://localhost:8000/api/public/paper-trading/open-positions/
```

### GET /api/public/paper-trading/summary/
System-wide comprehensive summary
```bash
curl http://localhost:8000/api/public/paper-trading/summary/
```

### GET /api/public/paper-trading/dashboard/
Complete dashboard with aggregated stats
```bash
curl http://localhost:8000/api/public/paper-trading/dashboard/
```

---

## 💻 Auto-Trading Developer Endpoints

### POST /api/dev/paper/start/
Start auto-trading with $1000 balance
```bash
curl -X POST -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"initial_balance": 1000}' \
  http://localhost:8000/api/dev/paper/start/
```

### GET /api/dev/paper/status/
Get auto-trading account status
```bash
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/api/dev/paper/status/
```

### POST /api/dev/paper/reset/
Reset account to initial state
```bash
curl -X POST -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/dev/paper/reset/
```

### GET /api/dev/paper/trades/
List all trades for auto-trading account
```bash
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/api/dev/paper/trades/
```

### GET /api/dev/paper/summary/
Comprehensive performance summary
```bash
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/api/dev/paper/summary/
```

### PATCH /api/dev/paper/settings/
Update auto-trading settings
```bash
curl -X PATCH -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"auto_trading_enabled": true, "min_signal_confidence": 0.75}' \
  http://localhost:8000/api/dev/paper/settings/
```

---

## 🚀 Quick Access URLs (Browser)

### User Dashboard (Login Required)
- Trades: http://localhost:8000/api/paper-trades/
- Performance: http://localhost:8000/api/paper-trades/performance/
- Open Positions: http://localhost:8000/api/paper-trades/open_positions/

### Public Dashboard (No Login)
- All Trades: http://localhost:8000/api/public/paper-trading/
- Performance: http://localhost:8000/api/public/paper-trading/performance/
- Open Positions: http://localhost:8000/api/public/paper-trading/open-positions/
- Dashboard: http://localhost:8000/api/public/paper-trading/dashboard/

### Auto-Trading (Login Required)
- Status: http://localhost:8000/api/dev/paper/status/
- Trades: http://localhost:8000/api/dev/paper/trades/
- Summary: http://localhost:8000/api/dev/paper/summary/

---

## 📊 Key Differences

| Feature | User Routes | Public Routes |
|---------|-------------|---------------|
| Auth | Required ✅ | Not Required ❌ |
| Data | Own trades only | All users' trades |
| URL Pattern | `/api/paper-trades/` | `/api/public/paper-trading/` |
| Use Case | Personal dashboard | Public showcase |
