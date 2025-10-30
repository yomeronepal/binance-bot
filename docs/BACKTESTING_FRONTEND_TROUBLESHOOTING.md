# Backtesting Frontend - Troubleshooting Guide

## Common Issues and Solutions

### Issue 1: "Can't access this page" or 404 Error

#### Cause
The backtesting page is behind authentication. You need to be logged in to access it.

#### Solution
1. Make sure you're logged in first
2. Navigate to: http://localhost:5173/login
3. Log in with your credentials
4. Then navigate to: http://localhost:5173/backtesting

**Full URL**: http://localhost:5173/backtesting (after login)

---

### Issue 2: Page Redirects to Dashboard

#### Cause
React Router catch-all redirects unknown routes to dashboard.

#### Solution
Make sure you're using the correct path:
- ✅ **Correct**: `/backtesting` (no trailing slash)
- ❌ Wrong: `/backtest`, `/back-testing`, `/backtesting/`

---

### Issue 3: Blank/White Screen

#### Cause
JavaScript error in the component or missing dependencies.

#### Solution

**Step 1: Check Browser Console**
1. Open browser DevTools (F12)
2. Go to Console tab
3. Look for red error messages
4. Share the error message if you see one

**Step 2: Verify Frontend is Running**
```bash
docker-compose ps frontend
```
Should show: `Up X minutes`

**Step 3: Check Frontend Logs**
```bash
docker-compose logs frontend --tail 50
```
Look for errors in red.

**Step 4: Restart Frontend**
```bash
docker-compose restart frontend
```

**Step 5: Force Rebuild**
If above doesn't work:
```bash
docker-compose down
docker-compose up -d --build frontend
```

---

### Issue 4: API Errors / No Data Loading

#### Symptoms
- Page loads but shows errors
- "Failed to fetch" messages
- Empty backtest list with errors

#### Cause
Backend API not accessible or authentication issues.

#### Solution

**Step 1: Verify Backend is Running**
```bash
docker-compose ps backend
```
Should show: `Up X minutes (healthy)`

**Step 2: Test Backend API Directly**
```bash
curl http://localhost:8000/api/backtest/
```

**Step 3: Check Your Auth Token**
1. Open DevTools (F12)
2. Go to Application → Local Storage → http://localhost:5173
3. Check if `accessToken` exists
4. If missing or expired, log out and log back in

**Step 4: Check CORS Settings**
Make sure backend allows frontend origin in `config/settings.py`:
```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
```

---

### Issue 5: Components Not Found Errors

#### Symptoms
Console shows: `Failed to resolve module` or `Cannot find module`

#### Cause
Files not properly created or paths incorrect.

#### Solution

**Step 1: Verify All Files Exist**
```bash
# Check page
ls client/src/pages/Backtesting.jsx

# Check store
ls client/src/store/useBacktestStore.js

# Check components
ls client/src/components/backtesting/*.jsx
```

All commands should show file exists. If any missing, the file wasn't created properly.

**Step 2: Rebuild Frontend**
```bash
cd client
npm run build
```

If build fails, you'll see the exact error.

---

### Issue 6: Navigation Link Not Showing

#### Cause
Layout component not updated or cache issue.

#### Solution

**Step 1: Hard Refresh Browser**
- Windows/Linux: `Ctrl + Shift + R`
- Mac: `Cmd + Shift + R`

**Step 2: Clear Browser Cache**
1. Open DevTools (F12)
2. Right-click refresh button
3. Select "Empty Cache and Hard Reload"

**Step 3: Verify Navigation Code**
Check [client/src/components/layout/Layout.jsx](d:\Project\binance-bot\client\src\components\layout\Layout.jsx) contains:
```jsx
<Link to="/backtesting" ...>
  Backtesting
</Link>
```

---

### Issue 7: Celery Tasks Not Running

#### Symptoms
- Backtest stays in PENDING status forever
- Status never changes from PENDING to RUNNING

#### Cause
Celery worker not running or tasks not registered.

#### Solution

**Step 1: Check Celery Worker Status**
```bash
docker-compose ps celery-worker
```

**Step 2: Verify Tasks are Registered**
```bash
docker-compose exec celery-worker celery -A config inspect registered | grep backtest
```

Should show:
```
* scanner.tasks.backtest_tasks.run_backtest_async
* scanner.tasks.backtest_tasks.run_optimization_async
* scanner.tasks.backtest_tasks.generate_recommendations_async
```

**Step 3: Restart Celery Worker**
```bash
docker-compose restart celery-worker
```

**See Also**: [BACKTESTING_CELERY_FIX.md](./BACKTESTING_CELERY_FIX.md)

---

### Issue 8: Chart Not Rendering

#### Symptoms
- Trades table shows but equity curve is blank
- "No equity curve data available" message

#### Cause
- Backtest didn't complete successfully
- Metrics endpoint returned empty data
- Recharts library issue

#### Solution

**Step 1: Verify Backtest Completed**
Check backtest status shows "COMPLETED" (green badge)

**Step 2: Check Browser Console**
Look for errors related to Recharts or chart rendering

**Step 3: Verify Data Exists**
Open DevTools → Network tab → Find request to `/api/backtest/:id/metrics/`
Check response has `equity_curve` array with data

**Step 4: Reinstall Dependencies**
```bash
cd client
npm install recharts
```

---

## Quick Diagnostic Commands

Run these to quickly check system status:

```bash
# All services status
docker-compose ps

# Backend health
curl http://localhost:8000/api/health/ || echo "Backend not accessible"

# Frontend accessibility
curl http://localhost:5173/ || echo "Frontend not accessible"

# Celery tasks
docker-compose exec celery-worker celery -A config inspect registered | grep backtest

# Check logs for errors
docker-compose logs backend --tail 20 | grep -i error
docker-compose logs frontend --tail 20 | grep -i error
docker-compose logs celery-worker --tail 20 | grep -i error
```

---

## Step-by-Step Access Guide

If you can't access the page at all, follow these steps:

### 1. Start All Services
```bash
cd /d/Project/binance-bot
docker-compose up -d
```

### 2. Wait for Services to be Ready (30 seconds)
```bash
# Check status
docker-compose ps
```
All should show "Up" status.

### 3. Access Frontend
Open browser: http://localhost:5173

### 4. Login
1. Click "Login" or go to http://localhost:5173/login
2. Enter your credentials (admin@example.com / admin123 or your credentials)
3. Click "Login"

### 5. Access Backtesting
After successful login, you should see the navigation menu.
Click "Backtesting" or navigate to: http://localhost:5173/backtesting

### 6. Expected Result
You should see:
- Three info cards at top (Total Backtests, Completed, Running)
- "New Backtest" button in top right
- Left sidebar with backtest list (may be empty)
- Right panel with "No Backtest Selected" message

---

## Still Having Issues?

If none of the above solutions work:

1. **Check Browser Console** (F12 → Console tab)
   - Copy any red error messages

2. **Check Backend Logs**
   ```bash
   docker-compose logs backend --tail 100
   ```

3. **Check Frontend Logs**
   ```bash
   docker-compose logs frontend --tail 100
   ```

4. **Full System Restart**
   ```bash
   docker-compose down
   docker-compose up -d
   # Wait 30 seconds
   docker-compose ps  # All should be "Up"
   ```

5. **Verify File Permissions**
   ```bash
   ls -la client/src/pages/Backtesting.jsx
   ls -la client/src/components/backtesting/
   ```
   Files should be readable.

6. **Rebuild Everything**
   ```bash
   docker-compose down -v  # Remove volumes
   docker-compose build --no-cache frontend
   docker-compose up -d
   ```

---

## Contact Information

If you're still stuck, provide the following information:

1. What URL are you trying to access?
2. Are you logged in?
3. What error message do you see (exact text)?
4. Browser console errors (if any)
5. Output of: `docker-compose ps`
6. Output of: `docker-compose logs frontend --tail 30`

---

## Quick Reference URLs

- **Frontend**: http://localhost:5173
- **Login Page**: http://localhost:5173/login
- **Backtesting Page**: http://localhost:5173/backtesting (requires login)
- **Backend API**: http://localhost:8000/api/backtest/
- **Admin Panel**: http://localhost:8000/admin/

---

**Last Updated**: 2025-10-30
