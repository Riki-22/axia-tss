# ================================================================
# Windows Auto Logon Configuration Script
# ================================================================
# Purpose: Enable automatic logon for Administrator account
# Security: Password is stored in registry (use at your own risk)
# ================================================================

# Check Administrator privileges
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run with Administrator privileges" -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Windows Auto Logon Configuration" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Prompt for password
Write-Host "Enter Administrator password for auto logon:" -ForegroundColor Yellow
$password = Read-Host -AsSecureString
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
$plainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

# Configure auto logon in registry
$RegPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"

try {
    Set-ItemProperty -Path $RegPath -Name "AutoAdminLogon" -Value "1"
    Set-ItemProperty -Path $RegPath -Name "DefaultUserName" -Value "Administrator"
    Set-ItemProperty -Path $RegPath -Name "DefaultPassword" -Value $plainPassword
    Set-ItemProperty -Path $RegPath -Name "AutoLogonCount" -Value "999999"
    
    Write-Host "`nOK Auto logon configured successfully" -ForegroundColor Green
    Write-Host "  - User: Administrator" -ForegroundColor White
    Write-Host "  - Auto logon: Enabled" -ForegroundColor White
    Write-Host "  - Max count: 999999" -ForegroundColor White
    
    # Verify settings
    Write-Host "`nVerifying configuration..." -ForegroundColor Cyan
    $config = Get-ItemProperty -Path $RegPath | Select-Object AutoAdminLogon, DefaultUserName
    if ($config.AutoAdminLogon -eq "1" -and $config.DefaultUserName -eq "Administrator") {
        Write-Host "OK Configuration verified" -ForegroundColor Green
    } else {
        Write-Host "WARNING: Verification failed" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "ERROR: Failed to configure auto logon" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Restart EC2 to test: Restart-Computer" -ForegroundColor White
Write-Host "  2. Wait 2-3 minutes after restart" -ForegroundColor White
Write-Host "  3. RDP reconnect (should auto-login)" -ForegroundColor White
Write-Host "  4. Verify all processes started" -ForegroundColor White
Write-Host "`nSECURITY WARNING:" -ForegroundColor Red
Write-Host "  Password is stored in registry in plain text" -ForegroundColor Yellow
Write-Host "  Only use in trusted environments (private EC2)" -ForegroundColor Yellow
Write-Host "========================================`n" -ForegroundColor Cyan

# Clear password from memory
$plainPassword = $null
[System.GC]::Collect()