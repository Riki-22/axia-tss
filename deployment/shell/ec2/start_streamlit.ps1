# ================================================================
# AXIA Streamlit UI Startup Script
# ================================================================

# Environment variables
$PROJECT_ROOT = "C:\Users\Administrator\Projects\axia-tss"
$CONDA_ROOT = "C:\ProgramData\miniconda3"
$CONDA_ENV = "axia-env"
$CONDA_ENV_PATH = "$CONDA_ROOT\envs\$CONDA_ENV"
$PYTHON_EXE = "$CONDA_ENV_PATH\python.exe"
$STREAMLIT_EXE = "$CONDA_ENV_PATH\Scripts\streamlit.exe"
$LOG_DIR = "C:\Users\Administrator\axia-logs"
$LOG_FILE = "$LOG_DIR\streamlit.log"
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
Add-Content -Path $LOG_FILE -Value "`n========================================`n[$timestamp] Streamlit UI startup initiated`n========================================"

try {
    # Move to project directory
    Set-Location $PROJECT_ROOT
    
    # Verify Python/Streamlit executables
    if (-not (Test-Path $PYTHON_EXE)) {
        Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] ERROR: Python executable not found: $PYTHON_EXE"
        exit 1
    }
    
    if (-not (Test-Path $STREAMLIT_EXE)) {
        Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] ERROR: Streamlit executable not found: $STREAMLIT_EXE"
        exit 1
    }
    
    # Check .env file
    if (Test-Path "$PROJECT_ROOT\.env") {
        Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] .env file detected"
    } else {
        Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] WARNING: .env file not found"
    }
    
    # Start Streamlit (background execution)
    Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] Executing Streamlit startup command"
    Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] Executable: $STREAMLIT_EXE"
    
    # Set PYTHONPATH (CRITICAL for module imports)
    $env:PYTHONPATH = $PROJECT_ROOT
    Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] PYTHONPATH: $env:PYTHONPATH"
    
    # Start Streamlit as background process
    $process = Start-Process -FilePath $STREAMLIT_EXE `
        -ArgumentList "run", "src\presentation\ui\streamlit\app.py", "--server.port", "8501", "--server.headless", "true" `
        -WorkingDirectory $PROJECT_ROOT `
        -RedirectStandardOutput "$LOG_DIR\streamlit_stdout.log" `
        -RedirectStandardError "$LOG_DIR\streamlit_stderr.log" `
        -NoNewWindow `
        -PassThru
    
    Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] Streamlit started successfully (PID: $($process.Id))"
    Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] Access URL: http://localhost:8501"
    
    # Verify startup (wait 5 seconds)
    Start-Sleep -Seconds 5
    
    if (-not $process.HasExited) {
        Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] OK Streamlit process running normally"
        exit 0
    } else {
        Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] ERROR: Streamlit process terminated"
        exit 1
    }
    
} catch {
    $errorMsg = $_.Exception.Message
    Add-Content -Path $LOG_FILE -Value "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))] ERROR: $errorMsg"
    Add-Content -Path $LOG_FILE -Value $_.ScriptStackTrace
    exit 1
}