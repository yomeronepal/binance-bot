# Docker Storage Migration Script
# Moves Docker Desktop WSL2 data to D:\docker
# Run this script as Administrator in PowerShell

param(
    [string]$TargetPath = "D:\docker",
    [switch]$SkipBackup = $false,
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"

# Color output functions
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

function Write-Success { Write-ColorOutput Green $args }
function Write-Warning { Write-ColorOutput Yellow $args }
function Write-Error { Write-ColorOutput Red $args }
function Write-Info { Write-ColorOutput Cyan $args }

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "This script must be run as Administrator!"
    Write-Info "Right-click PowerShell and select 'Run as Administrator'"
    exit 1
}

Write-Info "========================================"
Write-Info "Docker Storage Migration Tool"
Write-Info "========================================"
Write-Info "Target Location: $TargetPath"
Write-Info ""

# Step 1: Check prerequisites
Write-Info "[Step 1/7] Checking prerequisites..."

# Check WSL
try {
    $wslVersion = wsl --version 2>&1
    Write-Success "✓ WSL is installed"
} catch {
    Write-Error "✗ WSL is not installed or not in PATH"
    exit 1
}

# Check Docker Desktop
$dockerDesktopProcess = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
if ($dockerDesktopProcess) {
    Write-Warning "Docker Desktop is running"
} else {
    Write-Info "Docker Desktop is not running"
}

# Step 2: Check current WSL distributions
Write-Info "`n[Step 2/7] Checking Docker WSL distributions..."
$wslList = wsl --list -v | Out-String
Write-Info $wslList

$hasDockerData = $wslList -match "docker-desktop-data"
if ($hasDockerData) {
    Write-Success "✓ Found docker-desktop-data distribution"
} else {
    Write-Error "✗ docker-desktop-data not found"
    Write-Info "Make sure Docker Desktop is installed and has been run at least once"
    exit 1
}

# Step 3: Stop Docker Desktop
Write-Info "`n[Step 3/7] Stopping Docker Desktop..."
if ($dockerDesktopProcess) {
    if ($DryRun) {
        Write-Info "[DRY RUN] Would stop Docker Desktop"
    } else {
        Write-Warning "Stopping Docker Desktop... This may take a moment"
        Stop-Process -Name "Docker Desktop" -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 5

        # Stop WSL
        wsl --shutdown
        Start-Sleep -Seconds 3
        Write-Success "✓ Docker Desktop stopped"
    }
} else {
    Write-Info "Docker Desktop already stopped"
}

# Step 4: Create target directory
Write-Info "`n[Step 4/7] Creating target directory structure..."
if ($DryRun) {
    Write-Info "[DRY RUN] Would create: $TargetPath"
    Write-Info "[DRY RUN] Would create: $TargetPath\wsl"
    Write-Info "[DRY RUN] Would create: $TargetPath\wsl\data"
} else {
    New-Item -ItemType Directory -Force -Path $TargetPath | Out-Null
    New-Item -ItemType Directory -Force -Path "$TargetPath\wsl" | Out-Null
    New-Item -ItemType Directory -Force -Path "$TargetPath\wsl\data" | Out-Null
    Write-Success "✓ Created directory structure at $TargetPath"
}

# Step 5: Export current Docker data
Write-Info "`n[Step 5/7] Exporting Docker data..."
$backupFile = "$TargetPath\docker-desktop-data-backup.tar"

if ($DryRun) {
    Write-Info "[DRY RUN] Would export to: $backupFile"
} else {
    if (-not $SkipBackup) {
        Write-Warning "Exporting Docker data... This may take several minutes"
        Write-Info "Backup location: $backupFile"

        wsl --export docker-desktop-data $backupFile

        if ($LASTEXITCODE -eq 0) {
            $backupSize = (Get-Item $backupFile).Length / 1GB
            Write-Success "✓ Export completed: $([math]::Round($backupSize, 2)) GB"
        } else {
            Write-Error "✗ Export failed"
            exit 1
        }
    } else {
        Write-Warning "Skipping backup (--SkipBackup flag set)"
    }
}

# Step 6: Unregister and import to new location
Write-Info "`n[Step 6/7] Moving Docker data to new location..."

if ($DryRun) {
    Write-Info "[DRY RUN] Would unregister docker-desktop-data"
    Write-Info "[DRY RUN] Would import to: $TargetPath\wsl\data"
} else {
    # Unregister old distribution
    Write-Info "Unregistering old distribution..."
    wsl --unregister docker-desktop-data

    if ($LASTEXITCODE -eq 0) {
        Write-Success "✓ Unregistered docker-desktop-data"
    } else {
        Write-Error "✗ Failed to unregister"
        exit 1
    }

    # Import to new location
    Write-Warning "Importing to new location... This may take several minutes"
    wsl --import docker-desktop-data "$TargetPath\wsl\data" $backupFile --version 2

    if ($LASTEXITCODE -eq 0) {
        Write-Success "✓ Import completed"
    } else {
        Write-Error "✗ Import failed"
        exit 1
    }
}

# Step 7: Update Docker Desktop settings
Write-Info "`n[Step 7/7] Updating Docker Desktop settings..."

$settingsPath = "$env:APPDATA\Docker\settings.json"
if (Test-Path $settingsPath) {
    if ($DryRun) {
        Write-Info "[DRY RUN] Would update: $settingsPath"
    } else {
        # Backup original settings
        Copy-Item $settingsPath "$settingsPath.backup" -Force

        # Read and parse JSON
        $settings = Get-Content $settingsPath | ConvertFrom-Json

        # Update paths (using forward slashes for JSON)
        $targetPathJson = $TargetPath -replace '\\', '/'
        $settings | Add-Member -NotePropertyName "dataFolder" -NotePropertyValue $targetPathJson -Force

        # Save updated settings
        $settings | ConvertTo-Json -Depth 100 | Set-Content $settingsPath

        Write-Success "✓ Updated settings.json"
        Write-Info "Backup saved: $settingsPath.backup"
    }
} else {
    Write-Warning "settings.json not found at $settingsPath"
}

# Cleanup
if (-not $DryRun -and -not $SkipBackup) {
    Write-Info "`n[Cleanup] Removing backup file..."
    $keepBackup = Read-Host "Keep backup file? (Y/n)"
    if ($keepBackup -eq "n" -or $keepBackup -eq "N") {
        Remove-Item $backupFile -Force
        Write-Success "✓ Backup file removed"
    } else {
        Write-Info "Backup kept at: $backupFile"
    }
}

# Final verification
Write-Info "`n========================================"
Write-Success "Migration Complete!"
Write-Info "========================================"
Write-Info ""
Write-Info "Next steps:"
Write-Info "1. Start Docker Desktop"
Write-Info "2. Wait for it to fully initialize"
Write-Info "3. Verify with: docker info | grep 'Docker Root Dir'"
Write-Info "4. Check WSL location: wsl --list -v"
Write-Info ""
Write-Warning "Important: If Docker Desktop fails to start:"
Write-Info "- Restore from backup: $backupFile"
Write-Info "- Check Windows Event Viewer for errors"
Write-Info "- Try resetting Docker Desktop to defaults"
Write-Info ""

# Display new location
Write-Info "New Docker data location:"
Write-Success "  $TargetPath\wsl\data"
Write-Info ""

# Prompt to start Docker Desktop
$startDocker = Read-Host "Start Docker Desktop now? (Y/n)"
if ($startDocker -ne "n" -and $startDocker -ne "N") {
    Write-Info "Starting Docker Desktop..."
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    Write-Info "Docker Desktop is starting... Please wait for initialization"
}
