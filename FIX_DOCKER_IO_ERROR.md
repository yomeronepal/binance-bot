# Fix Docker I/O Error

## Current Error

```
failed to solve: write /var/lib/desktop-containerd/daemon/io.containerd.metadata.v1.bolt/meta.db: input/output error
```

This is a **Docker Desktop storage corruption issue**. Here's how to fix it:

---

## Solution 1: Restart Docker Desktop (Quickest)

1. **Completely close Docker Desktop**
   - Right-click Docker Desktop icon in system tray
   - Click "Quit Docker Desktop"
   - Wait 10 seconds

2. **Reopen Docker Desktop**
   - Start Docker Desktop
   - Wait for it to say "Docker Desktop is running"

3. **Try starting containers again**
   ```bash
   cd d:\Project\binance-bot
   docker-compose up -d
   ```

---

## Solution 2: Reset Docker Desktop (Recommended)

### Step 1: Open Docker Desktop Settings

1. Open Docker Desktop
2. Click the gear icon (Settings)
3. Go to "Troubleshoot" tab

### Step 2: Clean / Purge Data

Click **"Clean / Purge data"**
- This clears the cache but keeps images

OR click **"Reset to factory defaults"**
- This removes everything and starts fresh

### Step 3: Restart Docker Desktop

After reset, Docker will restart automatically.

### Step 4: Rebuild Your Containers

```bash
cd d:\Project\binance-bot
docker-compose build --no-cache
docker-compose up -d
```

---

## Solution 3: Increase Docker Resources

### If the error persists:

1. Open Docker Desktop Settings
2. Go to "Resources" → "Advanced"
3. Increase:
   - **Memory**: 4 GB minimum (8 GB recommended)
   - **Disk Space**: At least 20 GB free
   - **CPUs**: 2 minimum (4 recommended)

4. Click "Apply & Restart"

---

## Solution 4: WSL2 Backend Issue (Windows)

### If using WSL2:

1. **Check WSL2 is working**
   ```powershell
   wsl --list --verbose
   ```

2. **Restart WSL2**
   ```powershell
   wsl --shutdown
   ```

3. **Restart Docker Desktop**

4. **Try again**
   ```bash
   cd d:\Project\binance-bot
   docker-compose up -d
   ```

---

## Solution 5: Disk Space Check

### Check if you have enough disk space:

**Windows:**
```powershell
Get-PSDrive C | Select-Object Used,Free
```

**You need at least 10-20 GB free**

### If low on space:
1. Run Windows Disk Cleanup
2. Clear Docker cache:
   ```bash
   docker system prune -a -f
   ```

---

## Solution 6: Manual Docker Data Cleanup

### Windows Location:
```
C:\Users\<YourUsername>\AppData\Local\Docker
```

### Steps:
1. **Quit Docker Desktop completely**
2. **Delete Docker data folder** (⚠️ This removes all containers/images)
   ```powershell
   Remove-Item -Path "$env:LOCALAPPDATA\Docker" -Recurse -Force
   ```
3. **Restart Docker Desktop**
4. **Rebuild from scratch**

---

## After Docker is Fixed

### 1. Verify Docker is working:
```bash
docker run hello-world
```

### 2. Start your containers:
```bash
cd d:\Project\binance-bot
docker-compose up -d
```

### 3. Check container status:
```bash
docker-compose ps
```

### 4. Test management commands:
```bash
docker-compose exec backend python manage.py help
```

---

## Alternative: Test Commands Without Docker

If Docker continues to have issues, you can test the management commands directly in a Python environment:

### Setup Python Environment (Windows)

```bash
cd d:\Project\binance-bot\backend

# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set Django settings
set DJANGO_SETTINGS_MODULE=config.settings

# Test commands
python manage.py help
python manage.py analyze_trades --help
```

**Note:** You'll need PostgreSQL and Redis running locally for full functionality.

---

## Prevention

To avoid this issue in the future:

1. **Regular Docker maintenance**
   ```bash
   # Run weekly
   docker system prune -a
   ```

2. **Don't let Docker use all disk space**
   - Keep at least 20% free space
   - Set Docker's max disk usage in settings

3. **Restart Docker Desktop weekly**
   - Clears temporary issues
   - Prevents corruption

4. **Update Docker Desktop regularly**
   - Latest versions have bug fixes

---

## Summary of Steps

### Quick Fix (Try First):
1. Quit Docker Desktop
2. Wait 10 seconds
3. Restart Docker Desktop
4. Try `docker-compose up -d`

### If That Fails:
1. Docker Desktop → Settings → Troubleshoot
2. Click "Reset to factory defaults"
3. Wait for Docker to restart
4. Run `docker-compose build --no-cache`
5. Run `docker-compose up -d`

### If Still Failing:
1. Check disk space (need 20+ GB free)
2. Update Docker Desktop to latest version
3. Try Solution 6 (manual cleanup)
4. Restart computer
5. Reinstall Docker Desktop

---

## After Fix - Verify Everything Works

Once Docker is running, run the test script:

**Windows:**
```bash
test_commands.bat
```

**Or manually:**
```bash
docker-compose exec backend python manage.py help
docker-compose exec backend python manage.py analyze_trades --help
docker-compose exec backend python manage.py create_paper_account --help
```

---

## All Management Commands Are Ready!

Once Docker is working, you have these commands available:

1. ✅ `analyze_trades` - Trade analysis with TP/SL diagnostics
2. ✅ `analyze_performance` - Comprehensive performance review
3. ✅ `clean_database` - Database cleanup
4. ✅ `create_paper_account` - Paper account creation
5. ✅ `monitor_backtests` - Backtest monitoring

**Full documentation**: [docs/MANAGEMENT_COMMANDS.md](docs/MANAGEMENT_COMMANDS.md)

---

## Need Help?

If none of these solutions work:
1. Check Docker Desktop version (should be latest)
2. Check Windows updates
3. Try reinstalling Docker Desktop
4. Check Docker forums: https://forums.docker.com/
