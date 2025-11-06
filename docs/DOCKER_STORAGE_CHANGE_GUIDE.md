# Docker Storage Location Change Guide

## Change Docker Desktop Storage to D:/docker

### Method 1: Using Docker Desktop Settings (Recommended - GUI)

1. **Open Docker Desktop**
   - Click the Docker icon in system tray
   - Click the gear icon (Settings)

2. **Navigate to Resources → Advanced**
   - Click on "Resources" in the left sidebar
   - Click on "Advanced"

3. **Change Disk Image Location**
   - Look for "Disk image location" or "Virtual disk limit"
   - Click "Browse" and select `D:\docker`
   - Click "Apply & Restart"

4. **Wait for Docker to Restart**
   - Docker will move all data to the new location
   - This may take several minutes depending on your data size

---

### Method 2: Manual Configuration (Advanced)

#### Step 1: Stop All Containers and Docker Desktop

```bash
# Stop all running containers
docker-compose down

# Stop Docker Desktop
# Right-click Docker icon → Quit Docker Desktop
```

#### Step 2: Create D:/docker Directory

```powershell
# In PowerShell (Run as Administrator)
mkdir D:\docker
mkdir D:\docker\wsl
mkdir D:\docker\wsl\data
```

#### Step 3: Move WSL2 Docker Data

```powershell
# In PowerShell (Run as Administrator)

# Export current Docker Desktop data
wsl --export docker-desktop-data D:\docker\docker-desktop-data-backup.tar

# Unregister old WSL distribution
wsl --unregister docker-desktop-data

# Import to new location
wsl --import docker-desktop-data D:\docker\wsl\data D:\docker\docker-desktop-data-backup.tar --version 2

# Clean up backup file (optional)
del D:\docker\docker-desktop-data-backup.tar
```

#### Step 4: Update Docker Desktop Settings

**Option A: Via Settings.json**

Location: `%APPDATA%\Docker\settings.json`

Add or modify:
```json
{
  "dataFolder": "D:\\docker",
  "diskPath": "D:\\docker\\wsl\\data\\ext4.vhdx"
}
```

**Option B: Via daemon.json**

Location: `C:\ProgramData\Docker\config\daemon.json` (or `%USERPROFILE%\.docker\daemon.json`)

Add:
```json
{
  "data-root": "D:\\docker\\data",
  "storage-driver": "overlayfs"
}
```

#### Step 5: Start Docker Desktop

- Start Docker Desktop from Start Menu
- Wait for it to fully initialize
- Check the new location

---

### Method 3: Using WSL2 Configuration (Alternative)

If you're using WSL2 backend, you can configure WSL2 itself:

#### Create/Edit `.wslconfig` file

Location: `C:\Users\<YourUsername>\.wslconfig`

```ini
[wsl2]
# Move WSL2 VM disk to D: drive
vmLocation = "D:\\wsl"

# Set memory limit (optional)
memory = 8GB

# Set CPU limit (optional)
processors = 4

# Set swap size (optional)
swap = 2GB

# Disk size limit (optional)
diskSize = 256GB
```

**Note**: `.wslconfig` doesn't directly move Docker data, but it helps manage WSL2 resources.

---

## Verification Commands

After making changes, verify the new location:

```bash
# Check Docker info
docker info | grep "Docker Root Dir"

# Check WSL disk location (PowerShell)
wsl --list -v
Get-ChildItem D:\docker -Recurse | Measure-Object -Property Length -Sum

# Check available space
docker system df
```

---

## Current Storage Usage

Check your current Docker storage before migration:

```bash
# Total Docker storage usage
docker system df

# Detailed breakdown
docker system df -v

# Image sizes
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

# Container sizes
docker ps -as
```

---

## Rollback Instructions (If Needed)

If something goes wrong:

### Quick Rollback:

1. Quit Docker Desktop
2. Restore from backup:
   ```powershell
   wsl --unregister docker-desktop-data
   wsl --import docker-desktop-data C:\Users\<YourUsername>\AppData\Local\Docker\wsl\data D:\docker\docker-desktop-data-backup.tar --version 2
   ```
3. Restore `settings.json` from backup
4. Start Docker Desktop

---

## Important Notes

### Before You Start:

1. **Backup your data**: Export important containers/images
   ```bash
   docker save -o backup.tar image1 image2 image3
   docker export container_name > container_backup.tar
   ```

2. **Note current disk usage**:
   ```bash
   docker system df
   ```

3. **Ensure D: drive has enough space** (at least 50GB recommended)

4. **Stop all running containers**:
   ```bash
   docker-compose down
   docker stop $(docker ps -aq)
   ```

### After Migration:

1. **Verify all images are present**:
   ```bash
   docker images
   ```

2. **Verify volumes**:
   ```bash
   docker volume ls
   ```

3. **Restart your project**:
   ```bash
   cd D:\Project\binance-bot
   docker-compose up -d
   ```

---

## Troubleshooting

### Issue: "Access Denied" Error

**Solution**: Run PowerShell as Administrator

### Issue: WSL command not found

**Solution**: Install/Enable WSL2:
```powershell
wsl --install
wsl --set-default-version 2
```

### Issue: Docker Desktop won't start

**Solution**:
1. Check Windows Event Viewer for errors
2. Reset Docker Desktop: Settings → Reset → Reset to factory defaults
3. Manually restore data from backup

### Issue: Can't find docker-desktop-data

**Solution**:
```powershell
# List all WSL distributions
wsl --list -v

# Check if running
wsl --shutdown
```

---

## Quick Command Reference

```bash
# Check current Docker storage location
docker info | grep "Docker Root Dir"

# Check disk usage
docker system df

# Clean up unused data (free space)
docker system prune -a --volumes

# Export Docker Desktop data (backup)
wsl --export docker-desktop-data D:\backup\docker-data.tar

# Import Docker Desktop data
wsl --import docker-desktop-data D:\docker\wsl\data D:\backup\docker-data.tar --version 2

# Check WSL distributions
wsl --list -v

# Shutdown WSL (required before moving)
wsl --shutdown
```

---

## Recommended Approach

**For most users, I recommend Method 1 (Docker Desktop GUI)** as it:
- Automatically handles data migration
- Less prone to errors
- No manual file editing required
- Built-in safety checks

Use Method 2 or 3 only if you need fine-grained control or Method 1 doesn't work for your setup.
