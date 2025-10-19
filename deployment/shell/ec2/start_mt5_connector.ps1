# ================================================================
# AXIA MT5 Connector 起動スクリプト
# ================================================================
# 用途: MT5との接続を維持するプロセスを起動
# タスクスケジューラ: システム起動時に自動実行
# ================================================================

# 環境変数
$PROJECT_ROOT = "C:\Users\Administrator\Projects\axia-tss"
$MT5_TERMINAL_PATH = "C:\Program Files\Axiory MetaTrader 5\terminal64.exe"
$LOG_DIR = "C:\Users\Administrator\axia-logs"
$LOG_FILE = "$LOG_DIR\mt5_connector.log"
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
Add-Content -Path $LOG_FILE -Value "`n========================================`n[$timestamp] MT5 Connector 起動開始`n========================================"

try {
    # MT5が既に起動しているか確認
    $mt5Process = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
    
    if ($mt5Process) {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] MT5は既に起動中 (PID: $($mt5Process.Id))"
    } else {
        # MT5起動
        if (Test-Path $MT5_TERMINAL_PATH) {
            Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] MT5起動開始: $MT5_TERMINAL_PATH"
            
            $process = Start-Process -FilePath $MT5_TERMINAL_PATH -PassThru -WindowStyle Minimized
            
            Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] MT5起動成功 (PID: $($process.Id))"
            
            # 起動確認（10秒待機）
            Start-Sleep -Seconds 10
            
            $mt5Check = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
            if ($mt5Check) {
                Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ✓ MT5プロセス正常稼働中"
            } else {
                Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ✗ 警告: MT5プロセスが確認できません"
            }
        } else {
            Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ✗ エラー: MT5実行ファイルが見つかりません: $MT5_TERMINAL_PATH"
            exit 1
        }
    }
    
    # Python MT5接続モニター起動（オプション）
    # 注: 実際の接続モニタースクリプトがある場合は以下を有効化
    # Set-Location $PROJECT_ROOT
    # & conda activate axia-env
    # $monitorProcess = Start-Process -FilePath "python" `
    #     -ArgumentList "src\infrastructure\gateways\brokers\mt5\mt5_connector_monitor.py" `
    #     -WorkingDirectory $PROJECT_ROOT `
    #     -NoNewWindow `
    #     -PassThru
    # Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] MT5接続モニター起動 (PID: $($monitorProcess.Id))"
    
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ✓ MT5 Connector起動完了"
    exit 0
    
} catch {
    $errorMsg = $_.Exception.Message
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ✗ エラー発生: $errorMsg"
    Add-Content -Path $LOG_FILE -Value $_.ScriptStackTrace
    exit 1
}