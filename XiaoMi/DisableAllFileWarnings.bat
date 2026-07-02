@echo off
title Windows 安全警告永久关闭器 (增强版)
setlocal enabledelayedexpansion
color 0C
echo ======================================================
echo     Windows 安全警告永久关闭器
echo     将禁用：恶意文件警告 / SmartScreen / 附件标识
echo ======================================================
echo.

:: 自动请求管理员权限
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo 正在请求管理员权限...
    goto UACPrompt
) else ( goto gotAdmin )

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    del "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
    pushd "%CD%"
    CD /D "%~dp0"

:: 检查 Windows 版本
ver | find "10.0" >nul
if %errorlevel% equ 0 (
    set "WINVER=10"
) else (
    set "WINVER=old"
)

echo [1] 正在处理防篡改保护...
reg add "HKLM\SOFTWARE\Microsoft\Windows Defender\Features" /v "TamperProtection" /t REG_DWORD /d 0 /f >nul 2>nul
echo      提示：如果系统提示“防篡改已启用”，请手动进入
echo      Windows 安全中心 -> 病毒和威胁防护 -> 管理设置
echo      关闭“防篡改保护”后再运行本脚本，效果更彻底。
echo.

echo [2] 禁用 Microsoft Defender 实时保护（注册表）
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender" /v "DisableAntiSpyware" /t REG_DWORD /d 1 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection" /v "DisableRealtimeMonitoring" /t REG_DWORD /d 1 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection" /v "DisableBehaviorMonitoring" /t REG_DWORD /d 1 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection" /v "DisableOnAccessProtection" /t REG_DWORD /d 1 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection" /v "DisableScanOnRealtimeEnable" /t REG_DWORD /d 1 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Spynet" /v "SpynetReporting" /t REG_DWORD /d 0 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Spynet" /v "SubmitSamplesConsent" /t REG_DWORD /d 2 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\MpEngine" /v "MpEnablePus" /t REG_DWORD /d 0 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Policy Manager" /v "DisableAllNotifications" /t REG_DWORD /d 1 /f
echo     完成

echo [3] 关闭 SmartScreen（文件/应用/Edge）
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer" /v "SmartScreenEnabled" /t REG_SZ /d "Off" /f
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer" /v "SmartScreenEnabled" /t REG_SZ /d "Off" /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\SmartScreen" /v "SmartScreenEnabled" /t REG_DWORD /d 0 /f >nul 2>nul
reg add "HKLM\SOFTWARE\Policies\Microsoft\MicrosoftEdge\PhishingFilter" /v "EnabledV9" /t REG_DWORD /d 0 /f >nul 2>nul
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\AppHost" /v "EnableWebContentEvaluation" /t REG_DWORD /d 0 /f >nul 2>nul
echo     完成

echo [4] 禁用附件区域标识（Zones）及文件来源警告
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\Attachments" /v "SaveZoneInformation" /t REG_DWORD /d 1 /f
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\Attachments" /v "ScanWithAntiVirus" /t REG_DWORD /d 0 /f
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\Associations" /v "ModRiskFileTypes" /t REG_SZ /d "*.*" /f
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\Associations" /v "LowRiskFileTypes" /t REG_SZ /d "*.*" /f
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings\Zones\3" /v "1806" /t REG_DWORD /d 0 /f
echo     完成

echo [5] 停止并禁用 Defender 服务
sc stop WinDefend >nul 2>nul
sc config WinDefend start= disabled >nul 2>nul
sc stop WdNisSvc >nul 2>nul
sc config WdNisSvc start= disabled >nul 2>nul
sc stop WdBoot >nul 2>nul
sc config WdBoot start= disabled >nul 2>nul
sc stop WdFilter >nul 2>nul
sc stop WdNisDrv >nul 2>nul
echo     完成

echo [6] 禁用 Defender 计划任务（防止自动复活）
schtasks /Change /TN "Microsoft\Windows\Windows Defender\Windows Defender Cache Maintenance" /Disable >nul 2>nul
schtasks /Change /TN "Microsoft\Windows\Windows Defender\Windows Defender Cleanup" /Disable >nul 2>nul
schtasks /Change /TN "Microsoft\Windows\Windows Defender\Windows Defender Scheduled Scan" /Disable >nul 2>nul
schtasks /Change /TN "Microsoft\Windows\Windows Defender\Windows Defender Verification" /Disable >nul 2>nul
schtasks /Change /TN "Microsoft\Windows\Windows Defender\Windows Defender Threat Detection" /Disable >nul 2>nul
echo     完成

echo [7] 清理现有文件的 Zone.Identifier 标记（下载文件夹）
powershell -Command "Get-ChildItem -Path '%USERPROFILE%\Downloads' -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object { $zone = Get-Content -Stream Zone.Identifier -Path $_.FullName -ErrorAction SilentlyContinue; if($zone) { Remove-Item -Path $_.FullName -Stream Zone.Identifier -Force } }" >nul 2>nul
echo     完成

echo [8] 禁用 Windows 安全中心所有通知
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender Security Center\Notifications" /v "DisableNotifications" /t REG_DWORD /d 1 /f >nul 2>nul
reg add "HKCU\Software\Microsoft\Windows\Security Center" /v "NotificationsDisabled" /t REG_DWORD /d 1 /f >nul 2>nul
echo     完成

echo [9] 刷新组策略（立即生效部分设置）
gpupdate /force >nul 2>nul

echo.
echo ======================================================
echo 所有设置已完成！请【重启电脑】以完全生效。
echo 重启后，任何文件（包括恶意软件）都不会再弹出警告。
echo ======================================================
echo.
echo 如需恢复，请运行同目录下的 “RestoreWarnings.bat”
echo.
pause