# ================================================================
# AXIA Streamlit UI 起動スクリプト
# ================================================================
# 用途: Streamlit UIを起動し、ログローテーション付きで実行
# タスクスケジューラ: システム起動時に自動実行
# ================================================================

# 環境変数
$PROJECT_ROOT = "C:\Users\Administrator\Projects\axia-tss"
$CONDA_ENV_PATH = "C:\ProgramData\miniconda3\envs\axia-env"
$PYTHON_EXE = "$CONDA_ENV_PATH\python.exe"
$STREAMLIT_EXE = "$CONDA_ENV_PATH\Scripts\streamlit.exe"
$LOG_DIR = "C:\Users\Administrator\axia-logs"
$LOG_FILE = "$LOG_DIR\streamlit.log"
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
            # 既存ログをローテーション
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
            # 現在のログを .1 にリネーム
            Move-Item $LogPath "$LogPath.1" -Force
            Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ログローテーション完了: $LogPath" -ForegroundColor Yellow
        }
    }
}

# ログローテーション実行
Rotate-Log -LogPath $LOG_FILE

# ログ開始
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $LOG_FILE -Value "`n========================================`n[$timestamp] Streamlit UI 起動開始`n========================================"

try {
    # プロジェクトディレクトリに移動
    Set-Location $PROJECT_ROOT
    
    # Python/Streamlit実行ファイルの存在確認
    if (-not (Test-Path $PYTHON_EXE)) {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ✗ エラー: Python実行ファイルが見つかりません: $PYTHON_EXE"
        exit 1
    }
    
    if (-not (Test-Path $STREAMLIT_EXE)) {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ✗ エラー: Streamlit実行ファイルが見つかりません: $STREAMLIT_EXE"
        exit 1
    }
    
    # .envファイル読み込み確認
    if (Test-Path "$PROJECT_ROOT\.env") {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] .env ファイル検出"
    } else {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 警告: .env ファイルが見つかりません"
    }
    
    # Streamlit起動（バックグラウンドで実行）
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Streamlit起動コマンド実行"
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 実行ファイル: $STREAMLIT_EXE"
    
    # Streamlitをバックグラウンドプロセスとして起動
    $process = Start-Process -FilePath $STREAMLIT_EXE `
        -ArgumentList "run", "src\presentation\ui\streamlit\app.py", "--server.port", "8501", "--server.headless", "true" `
        -WorkingDirectory $PROJECT_ROOT `
        -RedirectStandardOutput "$LOG_DIR\streamlit_stdout.log" `
        -RedirectStandardError "$LOG_DIR\streamlit_stderr.log" `
        -NoNewWindow `
        -PassThru
    
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Streamlit起動成功 (PID: $($process.Id))"
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] アクセスURL: http://localhost:8501"
    
    # 起動確認（5秒待機）
    Start-Sleep -Seconds 5
    
    if (-not $process.HasExited) {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ✓ Streamlitプロセス正常稼働中"
        exit 0
    } else {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ✗ エラー: Streamlitプロセスが終了しました"
        exit 1
    }
    
} catch {
    $errorMsg = $_.Exception.Message
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ✗ エラー発生: $errorMsg"
    Add-Content -Path $LOG_FILE -Value $_.ScriptStackTrace
    exit 1
}