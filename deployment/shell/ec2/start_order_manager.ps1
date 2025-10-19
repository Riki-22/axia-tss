# ================================================================
# AXIA Order Manager Startup Script
# ================================================================

# Environment variables
$PROJECT_ROOT = "C:\Users\Administrator\Projects\axia-tss"
$CONDA_ROOT = "C:\ProgramData\miniconda3"
$CONDA_ENV = "axia-env"
$CONDA_ENV_PATH = "$CONDA_ROOT\envs\$CONDA_ENV"
$PYTHON_EXE = "$CONDA_ENV_PATH\python.exe"
$LOG_DIR = "C:\Users\Administrator\axia-logs"
$LOG_FILE = "$LOG_DIR\order_manager.log"
$MAX_LOG_SIZE = 10MB
$MAX_LOG_GENERATIONS = 5

# Initialize Conda (CRITICAL for Task Scheduler)
$env:Path = "$CONDA_ROOT;$CONDA_ROOT\Scripts;$CONDA_ROOT\Library\bin;$CONDA_ENV_PATH;$CONDA_ENV_PATH\Scripts;$env:Path"
$CONDA_HOOK = "$CONDA_ROOT\shell\condabin\conda-hook.ps1"
if (Test-Path $CONDA_HOOK) {
    . $CONDA_HOOK
}

# Log directory creation
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
}

# Log rotation function
function Rotate-Log {
    param([string]$LogPath)
    
    if (Test-Path $LogPath) {
        $fileInfo = Get-Item $LogPath
        if ($fileInfo.Length -gt $MAX_LOG_SIZE) {
            for ($i = $MAX_LOG_GENERATIONS - 1; $i -gt 0; $i--) {
                $oldLog = "$LogPath.$i"
                $newLog = "$LogPath.$($i + 1)"
                if (Test-Path $oldLog) {
                    if (Test-Path $newLog) {
                        Remove-Item $newLog -Force
                    }
                    Move-Item $oldLog $newLog -Force
                }
            }
            Move-Item $LogPath "$LogPath.1" -Force
            Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Log rotation completed: $LogPath" -ForegroundColor Yellow
        }
    }
}

# Execute log rotation
Rotate-Log -LogPath $LOG_FILE

# Log start
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $LOG_FILE -Value "`n========================================`n[$timestamp] Order Manager startup initiated`n========================================"

try {
    # Move to project directory
    Set-Location $PROJECT_ROOT
    
    # Verify Python executable
    if (-not (Test-Path $PYTHON_EXE)) {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERROR: Python executable not found: $PYTHON_EXE"
        exit 1
    }
    
    # Check .env file
    if (Test-Path "$PROJECT_ROOT\.env") {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] .env file detected"
    } else {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] WARNING: .env file not found"
    }
    
    # Start Order Manager
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Executing Order Manager startup command"
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Executable: $PYTHON_EXE"
    
    $process = Start-Process -FilePath $PYTHON_EXE `
        -ArgumentList "src\presentation\cli\run_order_processor.py" `
        -WorkingDirectory $PROJECT_ROOT `
        -RedirectStandardOutput "$LOG_DIR\order_manager_stdout.log" `
        -RedirectStandardError "$LOG_DIR\order_manager_stderr.log" `
        -NoNewWindow `
        -PassThru
    
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Order Manager started successfully (PID: $($process.Id))"
    
    # Verify startup (wait 5 seconds)
    Start-Sleep -Seconds 5
    
    if (-not $process.HasExited) {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] OK Order Manager process running normally"
        exit 0
    } else {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERROR: Order Manager process terminated"
        exit 1
    }
    
} catch {
    $errorMsg = $_.Exception.Message
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERROR: $errorMsg"
    Add-Content -Path $LOG_FILE -Value $_.ScriptStackTrace
    exit 1
}