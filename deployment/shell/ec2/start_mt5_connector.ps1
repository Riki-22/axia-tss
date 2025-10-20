# ================================================================
# AXIA MT5 Connector Startup Script
# ================================================================

# Environment variables
$PROJECT_ROOT = "C:\Users\Administrator\Projects\axia-tss"
$CONDA_ROOT = "C:\ProgramData\miniconda3"
$CONDA_ENV = "axia-env"
$CONDA_ENV_PATH = "$CONDA_ROOT\envs\$CONDA_ENV"
$MT5_TERMINAL_PATH = "C:\Program Files\Axiory MetaTrader 5\terminal64.exe"
$LOG_DIR = "C:\Users\Administrator\axia-logs"
$LOG_FILE = "$LOG_DIR\mt5_connector.log"
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
            Write-Host "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] Log rotation completed: $LogPath" -ForegroundColor Yellow
        }
    }
}

# Execute log rotation
Rotate-Log -LogPath $LOG_FILE

# Log start
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss 'UTC'")
Add-Content -Path $LOG_FILE -Value "`n========================================`n[$timestamp] MT5 Connector startup initiated`n========================================"

try {
    # Check if MT5 is already running
    $mt5Process = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
    
    if ($mt5Process) {
        Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] MT5 is already running (PID: $($mt5Process.Id))"
    } else {
        # Start MT5
        if (Test-Path $MT5_TERMINAL_PATH) {
            Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] Starting MT5: $MT5_TERMINAL_PATH"
            
            $process = Start-Process -FilePath $MT5_TERMINAL_PATH -PassThru -WindowStyle Minimized
            
            Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] MT5 started successfully (PID: $($process.Id))"
            
            # Wait for startup (10 seconds)
            Start-Sleep -Seconds 10
            
            $mt5Check = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
            if ($mt5Check) {
                Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] OK MT5 process running normally"
            } else {
                Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] WARNING: Cannot verify MT5 process"
            }
        } else {
            Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] ERROR: MT5 executable not found: $MT5_TERMINAL_PATH"
            exit 1
        }
    }
    
    Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] OK MT5 Connector startup completed"
    exit 0
    
} catch {
    $errorMsg = $_.Exception.Message
    Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] ERROR: $errorMsg"
    Add-Content -Path $LOG_FILE -Value $_.ScriptStackTrace
    exit 1
}