# ================================================================
# AXIA Data Collector 実行スクリプト
# ================================================================
# 用途: 日次データ収集（OHLCV）を実行
# タスクスケジューラ: 毎日 07:00 JST に実行
# ================================================================

# 環境変数
$PROJECT_ROOT = "C:\Users\Administrator\Projects\axia-tss"
$CONDA_ENV_PATH = "C:\ProgramData\miniconda3\envs\axia-env"
$PYTHON_EXE = "$CONDA_ENV_PATH\python.exe"
$LOG_DIR = "C:\Users\Administrator\axia-logs"
$LOG_FILE = "$LOG_DIR\data_collector.log"
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
Add-Content -Path $LOG_FILE -Value "`n========================================`n[$timestamp] Data Collector 実行開始`n========================================"

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
    
    # Data Collector実行
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Data Collector実行開始"
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 実行ファイル: $PYTHON_EXE"
    
    # 同期実行（完了まで待機）
    $output = & $PYTHON_EXE src\presentation\cli\run_data_collector.py 2>&1
    $exitCode = $LASTEXITCODE
    
    # 実行結果をログに記録
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ========== 実行ログ =========="
    Add-Content -Path $LOG_FILE -Value $output
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ========== 実行ログ終了 =========="
    
    if ($exitCode -eq 0) {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ✓ Data Collector実行成功"
        
        # Redis統計情報取得（オプション）
        try {
            $statsScript = "from src.infrastructure.persistence.redis.redis_client import RedisClient; client = RedisClient(); stats = client.get_cache_stats(); print(f'Redis Keys: {stats[`"total_keys`"]}, Memory: {stats[`"memory_used_mb`"]:.2f}MB')"
            $statsOutput = & $PYTHON_EXE -c $statsScript 2>&1
            Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Redis統計: $statsOutput"
        } catch {
            Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Redis統計取得スキップ"
        }
        
        exit 0
    } else {
        Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ✗ エラー: Data Collector実行失敗 (ExitCode: $exitCode)"
        exit 1
    }
    
} catch {
    $errorMsg = $_.Exception.Message
    Add-Content -Path $LOG_FILE -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ✗ エラー発生: $errorMsg"
    Add-Content -Path $LOG_FILE -Value $_.ScriptStackTrace
    exit 1
}