@echo off

echo 一定要 鼠标右键  - 管理员运行
echo 一定要 鼠标右键  - 管理员运行
echo 一定要 鼠标右键  - 管理员运行
echo. >> C:\Windows\System32\drivers\etc\hosts
echo #为小米刷机包下载,添加更快下载的节点 >> C:\Windows\System32\drivers\etc\hosts
echo 47.74.196.250 bigota.d.miui.com >> C:\Windows\System32\drivers\etc\hosts
echo 47.74.196.250 hugeota.d.miui.com >> C:\Windows\System32\drivers\etc\hosts
echo. >> C:\Windows\System32\drivers\etc\hosts

ipconfig /flushdns

::    ipconfig /release
::    ipconfig /renew
:: powershell.exe -ExecutionPolicy Bypass -File "D:\XiaoMi\DisableAllFileWarnings.ps1"

reg add "HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\usbflags\18D1D00D0100" /v "osvc" /t REG_BINARY /d "0000" /f
reg add "HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\usbflags\18D1D00D0100" /v "SkipContainerIdQuery" /t REG_BINARY /d "01000000" /f
reg add "HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\usbflags\18D1D00D0100" /v "SkipBOSDescriptorQuery" /t REG_BINARY /d "01000000" /f
echo.
echo 好了.现在可以关闭这个窗口了.
echo 好了.现在可以关闭这个窗口了.
echo 好了.现在可以关闭这个窗口了.
pause