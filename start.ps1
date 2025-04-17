# AUTO-TAG Docker Starter Script
[CmdletBinding()]
param (
    [Parameter(Position=0)]
    [ValidateSet("image", "folder", "status", "start", "stop", "")]
    [string]$Mode = "",
    
    [Parameter(Position=1)]
    [string]$Path = "",
    
    [switch]$Recursive,
    [ValidateSet("replace", "suffix")]
    [string]$SaveMode = "replace",
    [switch]$Help
)

$AppVersion = "1.0.0"
$ApiUrl = "http://localhost:8000"

function Show-Help {
    Write-Host "`nAUTO-TAG System - Help" -ForegroundColor Cyan
    Write-Host "=======================" -ForegroundColor Cyan
    Write-Host "`nUsage:`n"
    Write-Host "  .\start.ps1                       # Start AUTO-TAG service if not running"
    Write-Host "  .\start.ps1 image [image_path]    # Process a single image"
    Write-Host "  .\start.ps1 folder [folder_path]  # Process a folder of images"
    Write-Host "  .\start.ps1 status                # Check processing status"
    Write-Host "  .\start.ps1 stop                  # Stop AUTO-TAG service"
    Write-Host "`nOptions:`n"
    Write-Host "  -Recursive                        # Process folders recursively"
    Write-Host "  -SaveMode <replace|suffix>        # Save mode: replace original files or create new ones with suffix (default: replace)"
    Write-Host "  -Help                             # Show this help"
}

function Test-DockerInstallation {
    try {
        $dockerVersion = docker --version
        Write-Host "Docker is installed: $dockerVersion" -ForegroundColor Green
        
        # Check if Docker is running
        $dockerPs = docker ps | Out-String
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error: Docker is not running. Please start Docker Desktop." -ForegroundColor Red
            return $false
        }
        
        # Check NVIDIA container toolkit
        $nvidiaDocker = docker run --rm --gpus all nvidia/cuda:12.0.1-base-ubuntu22.04 nvidia-smi | Out-String
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Warning: NVIDIA Docker support is not properly configured. GPU acceleration will not be available." -ForegroundColor Yellow
            Write-Host "Please install the NVIDIA Container Toolkit: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html" -ForegroundColor Yellow
            return $true
        }
        
        Write-Host "NVIDIA Docker support is enabled" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "Error: Docker is not installed. Please install Docker Desktop with NVIDIA support." -ForegroundColor Red
        return $false
    }
}

function Start-AutoTagService {
    # Check if the service is already running
    $isRunning = docker ps | Select-String "autotag" | Out-String
    if ($isRunning) {
        Write-Host "AUTO-TAG service is already running" -ForegroundColor Green
        return $true
    }
    
    # Start the service
    Write-Host "Starting AUTO-TAG service..." -ForegroundColor Cyan
    docker-compose up -d
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error starting AUTO-TAG service" -ForegroundColor Red
        return $false
    }
    
    # Wait for the service to be ready
    Write-Host "Waiting for service to be ready..." -ForegroundColor Cyan
    $ready = $false
    $retries = 0
    $maxRetries = 30
    
    while (-not $ready -and $retries -lt $maxRetries) {
        try {
            $response = Invoke-WebRequest -Uri "$ApiUrl/status" -Method GET -UseBasicParsing
            if ($response.StatusCode -eq 200) {
                $ready = $true
            }
        }
        catch {
            Start-Sleep -Seconds 1
            $retries++
        }
    }
    
    if ($ready) {
        Write-Host "AUTO-TAG service is ready!" -ForegroundColor Green
        return $true
    }
    else {
        Write-Host "Timeout waiting for AUTO-TAG service to start" -ForegroundColor Red
        return $false
    }
}

function Stop-AutoTagService {
    Write-Host "Stopping AUTO-TAG service..." -ForegroundColor Cyan
    docker-compose down
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "AUTO-TAG service stopped" -ForegroundColor Green
        return $true
    }
    else {
        Write-Host "Error stopping AUTO-TAG service" -ForegroundColor Red
        return $false
    }
}

function Process-Image {
    param (
        [string]$ImagePath,
        [string]$SaveMode = "replace"
    )
    
    if (-not $ImagePath) {
        # Open file dialog
        Add-Type -AssemblyName System.Windows.Forms
        $openFileDialog = New-Object System.Windows.Forms.OpenFileDialog
        $openFileDialog.Filter = "Image files (*.jpg;*.jpeg;*.png)|*.jpg;*.jpeg;*.png"
        $openFileDialog.Title = "Select an image to process"
        
        if ($openFileDialog.ShowDialog() -eq "OK") {
            $ImagePath = $openFileDialog.FileName
        }
        else {
            Write-Host "Cancelled" -ForegroundColor Yellow
            return
        }
    }
    
    if (-not (Test-Path $ImagePath)) {
        Write-Host "Error: Image file not found: $ImagePath" -ForegroundColor Red
        return
    }
    
    # Ensure service is running
    if (-not (Start-AutoTagService)) {
        return
    }
    
    # Process the image
    Write-Host "Processing image: $ImagePath" -ForegroundColor Cyan
    
    try {
        $fileName = Split-Path -Leaf $ImagePath
        $fileBytes = [System.IO.File]::ReadAllBytes($ImagePath)
        $boundary = [System.Guid]::NewGuid().ToString()
        $LF = "`r`n"
        
        # Build multipart/form-data content
        $bodyLines = @(
            "--$boundary",
            "Content-Disposition: form-data; name=`"file`"; filename=`"$fileName`"",
            "Content-Type: application/octet-stream$LF"
        )
        
        $body = [System.Text.Encoding]::UTF8.GetBytes($bodyLines -join $LF)
        $body += $fileBytes
        $body += [System.Text.Encoding]::UTF8.GetBytes("$LF--$boundary--$LF")
        
        # Send request
        $headers = @{
            "Content-Type" = "multipart/form-data; boundary=$boundary"
        }
        
        $response = Invoke-RestMethod -Uri "$ApiUrl/process/image?save_mode=$SaveMode" -Method POST -Body $body -Headers $headers
        
        # Display results
        Write-Host "`nSuccessfully processed image: $fileName" -ForegroundColor Green
        Write-Host "Processing time: $($response.processing_time) seconds" -ForegroundColor Cyan
        Write-Host "Tags added: $($response.tags.Count)" -ForegroundColor Cyan
        
        if ($response.tags.Count -gt 0) {
            Write-Host "Tags: $($response.tags -join ', ')" -ForegroundColor White
        }
    }
    catch {
        Write-Host "Error processing image: $_" -ForegroundColor Red
    }
}

function Process-Folder {
    param (
        [string]$FolderPath,
        [bool]$ProcessRecursively,
        [string]$SaveMode = "replace"
    )
    
    if (-not $FolderPath) {
        # Open folder dialog
        Add-Type -AssemblyName System.Windows.Forms
        $folderDialog = New-Object System.Windows.Forms.FolderBrowserDialog
        $folderDialog.Description = "Select a folder with images to process"
        
        if ($folderDialog.ShowDialog() -eq "OK") {
            $FolderPath = $folderDialog.SelectedPath
        }
        else {
            Write-Host "Cancelled" -ForegroundColor Yellow
            return
        }
    }
    
    if (-not (Test-Path $FolderPath)) {
        Write-Host "Error: Folder not found: $FolderPath" -ForegroundColor Red
        return
    }
    
    # Ensure service is running
    if (-not (Start-AutoTagService)) {
        return
    }
    
    # Process the folder
    Write-Host "Processing folder: $FolderPath" -ForegroundColor Cyan
    if ($ProcessRecursively) {
        Write-Host "Including subfolders" -ForegroundColor Cyan
    }
    
    try {
        $params = @{
            path = $FolderPath
            recursive = $ProcessRecursively
            save_mode = $SaveMode
        }
        
        $response = Invoke-RestMethod -Uri "$ApiUrl/process/folder" -Method POST -Body $params
        
        Write-Host $response.message -ForegroundColor Green
        Write-Host "Processing started in background. Check status with: .\start.ps1 status" -ForegroundColor Cyan
    }
    catch {
        Write-Host "Error processing folder: $_" -ForegroundColor Red
    }
}

function Get-ProcessingStatus {
    # Ensure service is running
    if (-not (Start-AutoTagService)) {
        return
    }
    
    try {
        $status = Invoke-RestMethod -Uri "$ApiUrl/status" -Method GET
        
        Write-Host "`nProcessing Status:" -ForegroundColor Cyan
        
        if ($status.active) {
            Write-Host "  Active: Yes" -ForegroundColor Green
            Write-Host "  Folder: $($status.current_path)" -ForegroundColor White
            Write-Host "  Progress: $($status.processed_files)/$($status.total_files) files" -ForegroundColor White
            
            $percentComplete = 0
            if ($status.total_files -gt 0) {
                $percentComplete = [Math]::Round(($status.processed_files / $status.total_files) * 100, 1)
            }
            
            Write-Host "  Completion: $($percentComplete)%" -ForegroundColor White
            
            if ($status.eta_seconds -gt 0) {
                $eta = [TimeSpan]::FromSeconds($status.eta_seconds)
                if ($eta.TotalHours -ge 1) {
                    $etaStr = "{0:0}h {1:0}m {2:0}s" -f $eta.Hours, $eta.Minutes, $eta.Seconds
                }
                else {
                    $etaStr = "{0:0}m {1:0}s" -f $eta.Minutes, $eta.Seconds
                }
                Write-Host "  Estimated time remaining: $etaStr" -ForegroundColor White
            }
            
            Write-Host "  Current file: $($status.current_file)" -ForegroundColor White
            Write-Host "  Success rate: $($status.successful_files)/$($status.processed_files) files" -ForegroundColor White
        }
        else {
            Write-Host "  Active: No" -ForegroundColor Yellow
            
            if ($status.total_files -gt 0) {
                Write-Host "  Last job: $($status.current_path)" -ForegroundColor White
                Write-Host "  Completed: $($status.processed_files)/$($status.total_files) files" -ForegroundColor White
                Write-Host "  Success rate: $($status.successful_files)/$($status.processed_files) files" -ForegroundColor White
            }
            else {
                Write-Host "  No processing jobs have been run" -ForegroundColor White
            }
        }
    }
    catch {
        Write-Host "Error getting status: $_" -ForegroundColor Red
    }
}

# Main program

if ($Help) {
    Show-Help
    exit 0
}

# Check Docker installation
if (-not (Test-DockerInstallation)) {
    exit 1
}

# Process according to mode
switch ($Mode) {
    "image" {
        Process-Image -ImagePath $Path -SaveMode $SaveMode
    }
    "folder" {
        Process-Folder -FolderPath $Path -ProcessRecursively $Recursive -SaveMode $SaveMode
    }
    "status" {
        Get-ProcessingStatus
    }
    "start" {
        Start-AutoTagService
    }
    "stop" {
        Stop-AutoTagService
    }
    default {
        # Default: ensure service is running and show menu
        Start-AutoTagService | Out-Null
        
        $running = $true
        while ($running) {
            Write-Host "`n=====================================" -ForegroundColor Cyan
            Write-Host "           AUTO-TAG SYSTEM           " -ForegroundColor Cyan
            Write-Host "             Version $AppVersion     " -ForegroundColor Cyan
            Write-Host "=====================================" -ForegroundColor Cyan
            
            Write-Host "`n1. Process single image"
            Write-Host "2. Process folder"
            Write-Host "3. Check processing status"
            Write-Host "4. Configure save mode (current: $SaveMode)"
            Write-Host "5. Stop service"
            Write-Host "6. Exit"
            
            $choice = Read-Host "`nSelect an option (1-6)"
            
            switch ($choice) {
                "1" { Process-Image -SaveMode $SaveMode }
                "2" { Process-Folder -ProcessRecursively $false -SaveMode $SaveMode }
                "3" { Get-ProcessingStatus }
                "4" {
                    Write-Host "`nSelect save mode:" -ForegroundColor Cyan
                    Write-Host "1. Replace original files"
                    Write-Host "2. Create new files with '_tagged' suffix"
                    $saveModeChoice = Read-Host "`nSelect an option (1-2)"
                    
                    switch ($saveModeChoice) {
                        "1" { $SaveMode = "replace"; Write-Host "Save mode set to: replace original files" -ForegroundColor Green }
                        "2" { $SaveMode = "suffix"; Write-Host "Save mode set to: create new files with suffix" -ForegroundColor Green }
                        default { Write-Host "Invalid option. Save mode unchanged." -ForegroundColor Yellow }
                    }
                }
                "5" { Stop-AutoTagService; $running = $false }
                "6" { $running = $false }
                default {
                    Write-Host "`nInvalid option. Please select 1-6." -ForegroundColor Yellow
                    Start-Sleep -Seconds 1
                }
            }
            
            if ($running -and $choice -in 1..4) {
                Write-Host "`nPress any key to continue..."
                $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
            }
        }
    }
}