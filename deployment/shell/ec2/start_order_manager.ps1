# ================================================================
# AXIA Order Manager 起動スクリプト
# ================================================================
# 用途: SQS注文処理マネージャーを起動
# タスクスケジューラ: システム起動時に自動実行
# ================================================================

# 環境変数
$PROJECT_ROOT = "C:\Users\Administrator\Projects\axia-tss"
$CONDA_ENV_PATH = "C:\ProgramData\miniconda3\envs\axia-env"
$PYTHON_EXE = "$CONDA_ENV_PATH\python.exe"
$LOG_DIR = "C:\Users\Administrator\axia-logs"
$LOG_FILE = "$LOG_DIR\order_manager.log"
$MAX_LOG_SIZE = 10MB
$MAX_LOG_GENERATIONS = 5

# ログディレクトリ作成
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
}

# ログローテーション関数
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
            Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ログローテーション完了: $LogPath" -ForegroundColor Yellow
        }
    }
}

# ログローテーション実行
Rotate-Log -LogPath $LOG_FILE

# ログ開始
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $LOG_FILE -Value "`n========================================`n[$timestamp] Order Manager 起動開始`n========================================"

try {
    # プロジェクトディレクトリに移動
    Set-Location $PROJECT_ROOT
    
    # Python実行ファイルの存在確認
    if (-not (Test-Path $PYTHON_EXE)) {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ✗ エラー: Python実行ファイルが見つかりません: $PYTHON_EXE"
        exit 1
    }
    
    # .envファイル読み込み確認
    if (Test-Path "$PROJECT_ROOT\.env") {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] .env ファイル検出"
    } else {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 警告: .env ファイルが見つかりません"
    }
    
    # Order Manager起動
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Order Manager起動コマンド実行"
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 実行ファイル: $PYTHON_EXE"
    
    $process = Start-Process -FilePath $PYTHON_EXE `
        -ArgumentList "src\presentation\cli\run_order_processor.py" `
        -WorkingDirectory $PROJECT_ROOT `
        -RedirectStandardOutput "$LOG_DIR\order_manager_stdout.log" `
        -RedirectStandardError "$LOG_DIR\order_manager_stderr.log" `
        -NoNewWindow `
        -PassThru
    
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Order Manager起動成功 (PID: $($process.Id))"
    
    # 起動確認（5秒待機）
    Start-Sleep -Seconds 5
    
    if (-not $process.HasExited) {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ✓ Order Managerプロセス正常稼働中"
        exit 0
    } else {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ✗ エラー: Order Managerプロセスが終了しました"
        exit 1
    }
    
} catch {
    $errorMsg = $_.Exception.Message
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ✗ エラー発生: $errorMsg"
    Add-Content -Path $LOG_FILE -Value $_.ScriptStackTrace
    exit 1
}