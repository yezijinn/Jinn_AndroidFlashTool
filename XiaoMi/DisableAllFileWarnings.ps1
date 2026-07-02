# 需要以管理员身份运行
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "请以管理员身份运行此脚本。右键 -> 以 PowerShell 管理员身份运行" -ForegroundColor Red
    exit 1
}

Write-Host "正在禁用所有 Windows 文件安全警告..." -ForegroundColor Yellow

# 1. 禁用 Defender 实时保护（使用当前系统支持的参数）
try {
    Set-MpPreference -DisableRealtimeMonitoring $true -DisableBehaviorMonitoring $true -DisableBlockAtFirstSeen $true -DisableIOAVProtection $true -DisablePrivacyMode $true -DisableScriptScanning $true -SubmitSamplesConsent 2 -MAPSReporting 0 -DisableCatchupFullScan $true -DisableCatchupQuickScan $true -DisableArchiveScanning $true -DisableRemovableDriveScanning $true -DisableScanningMappedNetworkDrivesForFullScan $true -DisableScanningNetworkFiles $true -DisableNetworkProtection $true -PUAProtection Disabled -DisableTamperProtection $true -ErrorAction SilentlyContinue
    Write-Host "[OK] Defender 实时保护已禁用" -ForegroundColor Green
} catch {
    Write-Host "[警告] 部分 Defender 设置失败，可能是防篡改保护阻止" -ForegroundColor Yellow
}

# 2. 注册表禁用 Defender
$regPaths = @(
    "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender"
    "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection"
    "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Spynet"
    "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\MpEngine"
)
foreach ($path in $regPaths) {
    if (!(Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
}
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender" -Name "DisableAntiSpyware" -Value 1 -Type DWord -Force
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection" -Name "DisableRealtimeMonitoring" -Value 1 -Type DWord -Force
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection" -Name "DisableBehaviorMonitoring" -Value 1 -Type DWord -Force
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection" -Name "DisableOnAccessProtection" -Value 1 -Type DWord -Force
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection" -Name "DisableScanOnRealtimeEnable" -Value 1 -Type DWord -Force
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Spynet" -Name "SpynetReporting" -Value 0 -Type DWord -Force
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Spynet" -Name "SubmitSamplesConsent" -Value 2 -Type DWord -Force
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\MpEngine" -Name "MpEnablePus" -Value 0 -Type DWord -Force
Write-Host "[OK] 注册表禁用 Defender 完成" -ForegroundColor Green

# 3. 关闭 SmartScreen
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer" -Name "SmartScreenEnabled" -Value "Off" -Type String -Force
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer" -Name "SmartScreenEnabled" -Value "Off" -Type String -Force
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\SmartScreen" -Name "SmartScreenEnabled" -Value 0 -Type DWord -Force -ErrorAction SilentlyContinue
Write-Host "[OK] SmartScreen 已关闭" -ForegroundColor Green

# 4. 关闭附件区域标识
$attachmentsPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Policies\Attachments"
if (!(Test-Path $attachmentsPath)) { New-Item -Path $attachmentsPath -Force | Out-Null }
Set-ItemProperty -Path $attachmentsPath -Name "SaveZoneInformation" -Value 1 -Type DWord -Force
Set-ItemProperty -Path $attachmentsPath -Name "ScanWithAntiVirus" -Value 0 -Type DWord -Force

$associationsPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Policies\Associations"
if (!(Test-Path $associationsPath)) { New-Item -Path $associationsPath -Force | Out-Null }
Set-ItemProperty -Path $associationsPath -Name "ModRiskFileTypes" -Value "*.*" -Type String -Force

Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings\Zones\3" -Name "1806" -Value 0 -Type DWord -Force
Write-Host "[OK] 区域标识和附件警告已禁用" -ForegroundColor Green

# 5. 停止并禁用 Defender 服务
Stop-Service -Name WinDefend -Force -ErrorAction SilentlyContinue
Set-Service -Name WinDefend -StartupType Disabled -ErrorAction SilentlyContinue
Stop-Service -Name WdNisSvc -Force -ErrorAction SilentlyContinue
Set-Service -Name WdNisSvc -StartupType Disabled -ErrorAction SilentlyContinue
Write-Host "[OK] Defender 服务已禁用" -ForegroundColor Green

# 6. 禁用 Defender 计划任务
$tasks = @(
    "Microsoft\Windows\Windows Defender\Windows Defender Cache Maintenance",
    "Microsoft\Windows\Windows Defender\Windows Defender Cleanup",
    "Microsoft\Windows\Windows Defender\Windows Defender Scheduled Scan",
    "Microsoft\Windows\Windows Defender\Windows Defender Verification"
)
foreach ($task in $tasks) {
    Disable-ScheduledTask -TaskPath "\" -TaskName $task -ErrorAction SilentlyContinue
}
Write-Host "[OK] Defender 计划任务已禁用" -ForegroundColor Green

Write-Host "`n所有安全警告已禁用。请重启电脑。" -ForegroundColor Green
Read-Host "按 Enter 键退出"