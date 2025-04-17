# NVIDIA Container Toolkit Setup Script for Windows 11 Pro
# This script configures Docker Desktop to work with NVIDIA GPUs

[CmdletBinding()]
param (
    [switch]$Force,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

function Show-Help {
    Write-Host "`nNVIDIA Container Toolkit Setup for Docker Desktop" -ForegroundColor Cyan
    Write-Host "=================================================" -ForegroundColor Cyan
    Write-Host "`nThis script configures Docker Desktop to work with NVIDIA GPUs on Windows 11 Pro."
    Write-Host "`nRequirements:"
    Write-Host "  - Windows 11 Pro"
    Write-Host "  - Docker Desktop installed"
    Write-Host "  - NVIDIA GPU with updated drivers"
    Write-Host "  - Administrator privileges"
    Write-Host "`nUsage:"
    Write-Host "  .\setup-nvidia-docker.ps1         # Run the setup"
    Write-Host "  .\setup-nvidia-docker.ps1 -Force  # Force reconfiguration"
    Write-Host "  .\setup-nvidia-docker.ps1 -Help   # Show this help"
    Write-Host "`nAfter running this script, restart Docker Desktop for changes to take effect."
}

function Test-Administrator {
    $currentUser = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentUser.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-DockerDesktop {
    try {
        $dockerVersion = docker --version | Out-String
        if ($LASTEXITCODE -ne 0) {
            throw "Docker command not found"
        }
        
        # Check if Docker is running
        $dockerInfo = docker info | Out-String
        if ($LASTEXITCODE -ne 0) {
            throw "Docker is not running"
        }
        
        return $true
    }
    catch {
        return $false
    }
}

function Test-NvidiaGPU {
    try {
        # Check if NVIDIA GPU is present and drivers are installed
        $nvidiaDriver = Get-WmiObject Win32_PnPSignedDriver | Where-Object { $_.DeviceName -like "*NVIDIA*" -and $_.DeviceClass -eq "DISPLAY" }
        return $null -ne $nvidiaDriver
    }
    catch {
        return $false
    }
}

function Test-NvidiaToolkitAlreadyConfigured {
    try {
        # Test by trying to run a simple NVIDIA container
        $nvidiaDocker = docker run --rm --gpus all nvidia/cuda:12.0.1-base-ubuntu22.04 nvidia-smi | Out-String
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Update-DockerConfig {
    try {
        $configPath = "$env:USERPROFILE\.docker\daemon.json"
        $configDir = Split-Path -Parent $configPath
        
        # Create directory if it doesn't exist
        if (-not (Test-Path $configDir)) {
            New-Item -ItemType Directory -Path $configDir | Out-Null
        }
        
        # Create or update daemon.json
        if (Test-Path $configPath) {
            $config = Get-Content $configPath | ConvertFrom-Json
        }
        else {
            $config = [PSCustomObject]@{}
        }
        
        # Add NVIDIA runtime configuration
        $config | Add-Member -NotePropertyName "runtimes" -NotePropertyValue @{
            "nvidia" = @{
                "path" = "nvidia-container-runtime"
                "runtimeArgs" = @()
            }
        } -Force
        
        # Set default-runtime to nvidia
        $config | Add-Member -NotePropertyName "default-runtime" -NotePropertyValue "nvidia" -Force
        
        # Save the updated configuration
        $config | ConvertTo-Json -Depth 10 | Set-Content $configPath
        
        Write-Host "Docker configuration updated successfully!" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "Error updating Docker configuration: $_" -ForegroundColor Red
        return $false
    }
}

function Set-DockerDesktopSettings {
    try {
        $settingsPath = "$env:USERPROFILE\AppData\Roaming\Docker\settings.json"
        
        if (Test-Path $settingsPath) {
            $settings = Get-Content $settingsPath | ConvertFrom-Json
            
            # Enable WSL 2 integration
            $settings.wslEngineEnabled = $true
            
            # Enable NVIDIA GPU support
            $settings.wslGpuSupport = $true
            
            # Save settings
            $settings | ConvertTo-Json -Depth 10 | Set-Content $settingsPath
            
            Write-Host "Docker Desktop settings updated successfully!" -ForegroundColor Green
            return $true
        }
        else {
            Write-Host "Docker Desktop settings file not found. Please ensure Docker Desktop is installed." -ForegroundColor Yellow
            return $false
        }
    }
    catch {
        Write-Host "Error updating Docker Desktop settings: $_" -ForegroundColor Red
        return $false
    }
}

function Test-WindowsVersion {
    $osInfo = Get-CimInstance -ClassName Win32_OperatingSystem
    $versionMajor = [int]($osInfo.Version.Split(".")[0])
    $versionMinor = [int]($osInfo.Version.Split(".")[1])
    $isWin11 = $versionMajor -ge 10 -and $versionMinor -ge 0 -and $osInfo.BuildNumber -ge 22000
    
    # Check for Pro edition
    $isPro = $osInfo.Caption -like "*Pro*"
    
    return $isWin11 -and $isPro
}

function Install-NvidiaToolkit {
    Write-Host "`nConfigure Docker Desktop for NVIDIA GPU support" -ForegroundColor Cyan
    Write-Host "=============================================" -ForegroundColor Cyan
    
    # Check if running as administrator
    if (-not (Test-Administrator)) {
        Write-Host "Error: This script must be run as Administrator. Please restart with elevated privileges." -ForegroundColor Red
        return $false
    }
    
    # Check Windows version
    if (-not (Test-WindowsVersion)) {
        Write-Host "Error: This script requires Windows 11 Pro. Current OS is not compatible." -ForegroundColor Red
        return $false
    }
    
    # Check if Docker Desktop is installed and running
    if (-not (Test-DockerDesktop)) {
        Write-Host "Error: Docker Desktop is not installed or not running. Please install and start Docker Desktop first." -ForegroundColor Red
        return $false
    }
    
    # Check if NVIDIA GPU is present
    if (-not (Test-NvidiaGPU)) {
        Write-Host "Error: No NVIDIA GPU detected or drivers not installed. Please install the latest NVIDIA drivers." -ForegroundColor Red
        return $false
    }
    
    # Check if NVIDIA Container Toolkit is already configured
    if (Test-NvidiaToolkitAlreadyConfigured) {
        if (-not $Force) {
            Write-Host "NVIDIA Container Toolkit is already configured and working properly!" -ForegroundColor Green
            Write-Host "Use -Force to reconfigure if needed." -ForegroundColor Cyan
            return $true
        }
        else {
            Write-Host "NVIDIA Container Toolkit is already configured. Reconfiguring as requested..." -ForegroundColor Yellow
        }
    }
    
    # Update Docker configuration
    $configSuccess = Update-DockerConfig
    
    # Update Docker Desktop settings
    $settingsSuccess = Set-DockerDesktopSettings
    
    if ($configSuccess -and $settingsSuccess) {
        Write-Host "`nNVIDIA Container Toolkit configuration complete!" -ForegroundColor Green
        Write-Host "Please restart Docker Desktop for changes to take effect." -ForegroundColor Yellow
        
        # Prompt to restart Docker Desktop
        $restart = Read-Host "Would you like to restart Docker Desktop now? (y/n)"
        if ($restart -eq "y" -or $restart -eq "Y") {
            Write-Host "Stopping Docker Desktop..." -ForegroundColor Cyan
            Stop-Process -Name "Docker Desktop" -Force -ErrorAction SilentlyContinue
            
            Write-Host "Starting Docker Desktop..." -ForegroundColor Cyan
            Start-Process "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
            
            Write-Host "Docker Desktop is restarting. Please wait a few moments for it to initialize." -ForegroundColor Yellow
        }
        
        return $true
    }
    else {
        Write-Host "`nNVIDIA Container Toolkit configuration failed." -ForegroundColor Red
        return $false
    }
}

# Main script

if ($Help) {
    Show-Help
    exit 0
}

try {
    $result = Install-NvidiaToolkit
    if ($result) {
        Write-Host "`nAfter Docker Desktop restarts, verify configuration with the following command:" -ForegroundColor Cyan
        Write-Host "docker run --rm --gpus all nvidia/cuda:12.0.1-base-ubuntu22.04 nvidia-smi" -ForegroundColor White
        exit 0
    }
    else {
        exit 1
    }
}
catch {
    Write-Host "An unexpected error occurred: $_" -ForegroundColor Red
    exit 1
}