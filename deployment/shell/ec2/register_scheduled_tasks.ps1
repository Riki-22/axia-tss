# ================================================================
# AXIA Task Scheduler Registration Script
# ================================================================
# Purpose: Register 4 tasks to Windows Task Scheduler
# Execute: Run with Administrator privileges in PowerShell
# ================================================================

# Check Administrator privileges
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run with Administrator privileges" -ForegroundColor Red
    Write-Host "Please right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# Environment variables
$PROJECT_ROOT = "C:\Users\Administrator\Projects\axia-tss"
$SCRIPT_DIR = "$PROJECT_ROOT\deployment\shell\ec2"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "AXIA Task Scheduler Registration Started" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Remove existing tasks if they exist
$existingTasks = @("AXIA_Streamlit", "AXIA_Order_Manager", "AXIA_MT5", "AXIA_Data_Collector")
foreach ($taskName in $existingTasks) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host "[DELETE] Existing task: $taskName" -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
}

# ========================================
# Task 1: AXIA_Streamlit
# ========================================
Write-Host "`n[1/4] Registering AXIA_Streamlit..." -ForegroundColor Green

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

Write-Host "OK AXIA_Streamlit registered" -ForegroundColor Green

# ========================================
# Task 2: AXIA_Order_Manager
# ========================================
Write-Host "`n[2/4] Registering AXIA_Order_Manager..." -ForegroundColor Green

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

Write-Host "OK AXIA_Order_Manager registered" -ForegroundColor Green

# ========================================
# Task 3: AXIA_MT5
# ========================================
Write-Host "`n[3/4] Registering AXIA_MT5..." -ForegroundColor Green

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

Write-Host "OK AXIA_MT5 registered" -ForegroundColor Green

# ========================================
# Task 4: AXIA_Data_Collector
# ========================================
Write-Host "`n[4/4] Registering AXIA_Data_Collector..." -ForegroundColor Green

$action4 = New-ScheduledTaskAction `
    -Execute "PowerShell.exe" `
    -Argument "-ExecutionPolicy Bypass -NoProfile -File `"$SCRIPT_DIR\run_data_collector.ps1`"" `
    -WorkingDirectory $PROJECT_ROOT

# Execute weekdays only (Monday-Friday) at 07:00 JST
$trigger4 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "07:00"

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
    -Description "AXIA Weekday Data Collection (Mon-Fri 07:00 JST)" | Out-Null

Write-Host "OK AXIA_Data_Collector registered (Weekdays only)" -ForegroundColor Green

# ========================================
# Verify registration
# ========================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Registered Tasks Verification" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$registeredTasks = Get-ScheduledTask | Where-Object { $_.TaskName -like "AXIA_*" }
foreach ($task in $registeredTasks) {
    $state = $task.State
    $stateColor = if ($state -eq "Ready") { "Green" } else { "Yellow" }
    Write-Host "  OK $($task.TaskName) [$state]" -ForegroundColor $stateColor
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Task Scheduler Registration Completed" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Open Task Scheduler: taskschd.msc" -ForegroundColor White
Write-Host "  2. Manually run each task to test" -ForegroundColor White
Write-Host "  3. Check logs: C:\Users\Administrator\axia-logs\" -ForegroundColor White
Write-Host "  4. EC2 reboot test: Restart-Computer" -ForegroundColor White