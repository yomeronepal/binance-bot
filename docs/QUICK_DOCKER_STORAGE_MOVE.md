# Quick Guide: Move Docker to D:/docker

## Easiest Method (Recommended for most users)

### Using Docker Desktop GUI:

1. **Open Docker Desktop Settings**
   - Right-click Docker icon in system tray
   - Click Settings (gear icon)

2. **Go to Resources → Advanced**

3. **Change Disk Image Location**
   - Browse to `D:\docker`
   - Click "Apply & Restart"
   - Wait for migration (5-15 minutes)

**Done!** Docker will automatically move everything.

---

## Alternative: Using PowerShell Script

We've provided an automated script for you:

### Quick Steps:

1. **Open PowerShell as Administrator**
   - Search "PowerShell" in Start Menu
   - Right-click → "Run as Administrator"

2. **Navigate to project**
   ```powershell
   cd D:\Project\binance-bot
   ```

3. **Run migration script**
   ```powershell
   .\migrate-docker-storage.ps1
   ```

4. **Follow the prompts**

### Script Options:

```powershell
# Dry run (see what would happen without doing it)
.\migrate-docker-storage.ps1 -DryRun

# Custom location
.\migrate-docker-storage.ps1 -TargetPath "E:\docker-data"

# Skip backup (faster, but risky)
.\migrate-docker-storage.ps1 -SkipBackup
```

---

## Manual Method (If script fails)

### Step 1: Stop Docker
```powershell
# Quit Docker Desktop from system tray
wsl --shutdown
```

### Step 2: Create directories
```powershell
mkdir D:\docker\wsl\data
```

### Step 3: Export & Move
```powershell
wsl --export docker-desktop-data D:\docker\backup.tar
wsl --unregister docker-desktop-data
wsl --import docker-desktop-data D:\docker\wsl\data D:\docker\backup.tar --version 2
```

### Step 4: Start Docker Desktop

---

## Verification

After migration, verify it worked:

```bash
# Check new location
docker info | grep "Docker Root Dir"

# Check WSL distributions
wsl --list -v

# Check your containers still work
cd D:\Project\binance-bot
docker-compose ps
```

---

## Troubleshooting

### Docker won't start after migration

**Solution 1**: Check Event Viewer
- Windows Key + X → Event Viewer
- Look for Docker errors

**Solution 2**: Restore from backup
```powershell
wsl --unregister docker-desktop-data
wsl --import docker-desktop-data C:\Users\<YourUsername>\AppData\Local\Docker\wsl\data D:\docker\backup.tar --version 2
```

**Solution 3**: Factory reset Docker Desktop
- Settings → Troubleshoot → Reset to factory defaults

### "Access Denied" error

Run PowerShell as Administrator

### WSL not found

Install WSL2:
```powershell
wsl --install
wsl --set-default-version 2
```

---

## After Migration

1. **Restart your project**:
   ```bash
   cd D:\Project\binance-bot
   docker-compose up -d
   ```

2. **Verify all containers are running**:
   ```bash
   docker-compose ps
   ```

3. **Check signals are still being generated**:
   ```bash
   docker-compose exec backend python manage.py shell -c "from signals.models import Signal; print(f'Active signals: {Signal.objects.filter(status=\"ACTIVE\").count()}')"
   ```

---

## Space Savings

After migration, you can free up space on C: drive:

```powershell
# Check old location size (before deletion)
$oldPath = "C:\Users\$env:USERNAME\AppData\Local\Docker\wsl"
if (Test-Path $oldPath) {
    $size = (Get-ChildItem $oldPath -Recurse | Measure-Object -Property Length -Sum).Sum / 1GB
    Write-Host "Old Docker data: $([math]::Round($size, 2)) GB"
}
```

**Note**: The migration script removes old data automatically after successful import.

---

## Need Help?

Files created for you:
- [DOCKER_STORAGE_CHANGE_GUIDE.md](DOCKER_STORAGE_CHANGE_GUIDE.md) - Detailed guide with all methods
- [migrate-docker-storage.ps1](migrate-docker-storage.ps1) - Automated migration script
- This file - Quick reference

Choose the method that works best for you!
