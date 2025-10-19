# ================================================================
# AXIA Data Collector Execution Script
# ================================================================

# Environment variables
$PROJECT_ROOT = "C:\Users\Administrator\Projects\axia-tss"
$CONDA_ROOT = "C:\ProgramData\miniconda3"
$CONDA_ENV = "axia-env"
$CONDA_ENV_PATH = "$CONDA_ROOT\envs\$CONDA_ENV"
$PYTHON_EXE = "$CONDA_ENV_PATH\python.exe"
$LOG_DIR = "C:\Users\Administrator\axia-logs"
$LOG_FILE = "$LOG_DIR\data_collector.log"
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
Add-Content -Path $LOG_FILE -Value "`n========================================`n[$timestamp] Data Collector execution initiated`n========================================"

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
    
    # Execute Data Collector
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Data Collector execution started"
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Executable: $PYTHON_EXE"
    
    # Set PYTHONPATH (CRITICAL for module imports)
    $env:PYTHONPATH = $PROJECT_ROOT
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] PYTHONPATH: $env:PYTHONPATH"

    # Synchronous execution (wait for completion)
    $output = & $PYTHON_EXE src\presentation\cli\run_data_collector.py 2>&1
    $exitCode = $LASTEXITCODE
    
    # Record execution results to log
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ========== Execution Log =========="
    Add-Content -Path $LOG_FILE -Value $output
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ========== Execution Log End =========="
    
    if ($exitCode -eq 0) {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] OK Data Collector execution successful"
        
        # Get Redis statistics (optional)
        try {
            $statsScript = "from src.infrastructure.persistence.redis.redis_client import RedisClient; client = RedisClient(); stats = client.get_cache_stats(); print(f'Redis Keys: {stats[`"total_keys`"]}, Memory: {stats[`"memory_used_mb`"]:.2f}MB')"
            $statsOutput = & $PYTHON_EXE -c $statsScript 2>&1
            Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Redis statistics: $statsOutput"
        } catch {
            Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Redis statistics retrieval skipped"
        }
        
        exit 0
    } else {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERROR: Data Collector execution failed (ExitCode: $exitCode)"
        exit 1
    }
    
} catch {
    $errorMsg = $_.Exception.Message
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERROR: $errorMsg"
    Add-Content -Path $LOG_FILE -Value $_.ScriptStackTrace
    exit 1
}