# ================================================================
# AXIA タスクスケジューラ一括登録スクリプト
# ================================================================
# 用途: 4つのタスクをWindows タスクスケジューラに登録
# 実行: 管理者権限のPowerShellで実行
# ================================================================

# 管理者権限チェック
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "エラー: このスクリプトは管理者権限で実行する必要があります" -ForegroundColor Red
    Write-Host "PowerShellを右クリック → '管理者として実行' で開き直してください" -ForegroundColor Yellow
    exit 1
}

# 環境変数
$PROJECT_ROOT = "C:\Users\Administrator\Projects\axia-tss"
$SCRIPT_DIR = "$PROJECT_ROOT\deployment\shell"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "AXIA タスクスケジューラ登録開始" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# 既存タスクを削除（存在する場合）
$existingTasks = @("AXIA_Streamlit", "AXIA_Order_Manager", "AXIA_MT5", "AXIA_Data_Collector")
foreach ($taskName in $existingTasks) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host "[削除] 既存タスク: $taskName" -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
}

# ========================================
# Task 1: AXIA_Streamlit
# ========================================
Write-Host "`n[1/4] AXIA_Streamlit 登録中..." -ForegroundColor Green

$action1 = New-ScheduledTaskAction `
    -Execute "PowerShell.exe" `
    -Argument "-ExecutionPolicy Bypass -NoProfile -File `"$SCRIPT_DIR\start_streamlit.ps1`"" `
    -WorkingDirectory $PROJECT_ROOT

$trigger1 = New-ScheduledTaskTrigger -AtStartup

$principal1 = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

$settings1 = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

Register-ScheduledTask `
    -TaskName "AXIA_Streamlit" `
    -Action $action1 `
    -Trigger $trigger1 `
    -Principal $principal1 `
    -Settings $settings1 `
    -Description "AXIA Streamlit UI (Port: 8501)" | Out-Null

Write-Host "✓ AXIA_Streamlit 登録完了" -ForegroundColor Green

# ========================================
# Task 2: AXIA_Order_Manager
# ========================================
Write-Host "`n[2/4] AXIA_Order_Manager 登録中..." -ForegroundColor Green

$action2 = New-ScheduledTaskAction `
    -Execute "PowerShell.exe" `
    -Argument "-ExecutionPolicy Bypass -NoProfile -File `"$SCRIPT_DIR\start_order_manager.ps1`"" `
    -WorkingDirectory $PROJECT_ROOT

$trigger2 = New-ScheduledTaskTrigger -AtStartup

$principal2 = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

$settings2 = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

Register-ScheduledTask `
    -TaskName "AXIA_Order_Manager" `
    -Action $action2 `
    -Trigger $trigger2 `
    -Principal $principal2 `
    -Settings $settings2 `
    -Description "AXIA SQS Order Processor" | Out-Null

Write-Host "✓ AXIA_Order_Manager 登録完了" -ForegroundColor Green

# ========================================
# Task 3: AXIA_MT5
# ========================================
Write-Host "`n[3/4] AXIA_MT5 登録中..." -ForegroundColor Green

$action3 = New-ScheduledTaskAction `
    -Execute "PowerShell.exe" `
    -Argument "-ExecutionPolicy Bypass -NoProfile -File `"$SCRIPT_DIR\start_mt5_connector.ps1`"" `
    -WorkingDirectory $PROJECT_ROOT

$trigger3 = New-ScheduledTaskTrigger -AtStartup

$principal3 = New-ScheduledTaskPrincipal `
    -UserId "Administrator" `
    -LogonType Interactive `
    -RunLevel Highest

$settings3 = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

Register-ScheduledTask `
    -TaskName "AXIA_MT5" `
    -Action $action3 `
    -Trigger $trigger3 `
    -Principal $principal3 `
    -Settings $settings3 `
    -Description "AXIA MT5 Connection Manager" | Out-Null

Write-Host "✓ AXIA_MT5 登録完了" -ForegroundColor Green

# ========================================
# Task 4: AXIA_Data_Collector
# ========================================
Write-Host "`n[4/4] AXIA_Data_Collector 登録中..." -ForegroundColor Green

$action4 = New-ScheduledTaskAction `
    -Execute "PowerShell.exe" `
    -Argument "-ExecutionPolicy Bypass -NoProfile -File `"$SCRIPT_DIR\run_data_collector.ps1`"" `
    -WorkingDirectory $PROJECT_ROOT

# 毎日 07:00 JST に実行
$trigger4 = New-ScheduledTaskTrigger -Daily -At "07:00"

$principal4 = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

$settings4 = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask `
    -TaskName "AXIA_Data_Collector" `
    -Action $action4 `
    -Trigger $trigger4 `
    -Principal $principal4 `
    -Settings $settings4 `
    -Description "AXIA Daily Data Collection (07:00 JST)" | Out-Null

Write-Host "✓ AXIA_Data_Collector 登録完了" -ForegroundColor Green

# ========================================
# 登録確認
# ========================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "登録タスク確認" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$registeredTasks = Get-ScheduledTask | Where-Object { $_.TaskName -like "AXIA_*" }
foreach ($task in $registeredTasks) {
    $state = $task.State
    $stateColor = if ($state -eq "Ready") { "Green" } else { "Yellow" }
    Write-Host "  ✓ $($task.TaskName) [$state]" -ForegroundColor $stateColor
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "タスクスケジューラ登録完了" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "次のステップ:" -ForegroundColor Yellow
Write-Host "  1. タスクスケジューラを開いて確認: taskschd.msc" -ForegroundColor White
Write-Host "  2. 各タスクを手動実行してテスト" -ForegroundColor White
Write-Host "  3. ログ確認: C:\Users\Administrator\axia-logs\" -ForegroundColor White
Write-Host "  4. EC2再起動テスト: Restart-Computer" -ForegroundColor White