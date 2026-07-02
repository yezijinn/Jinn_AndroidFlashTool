#!/usr/bin/env python3
"""小米刷机助手 - 一键编译脚本 (含UPX加壳 + 完整性校验)"""

import os
import sys
import shutil
import subprocess
import hashlib
import base64

UPX_DIR = os.path.join(os.path.dirname(__file__), 'upx')

def _find_upx():
    for root, dirs, files in os.walk(UPX_DIR):
        for f in files:
            if f.lower() == 'upx.exe':
                return os.path.join(root, f)
    return None

def _append_hash(exe_path):
    """计算SHA256并追加到exe末尾"""
    with open(exe_path, 'rb') as f:
        data = f.read()
    h = base64.b64encode(hashlib.sha256(data).digest()).decode()  # 44 chars
    with open(exe_path, 'ab') as f:
        f.write(h.encode('ascii'))
    return h

def main():
    print("=" * 50)
    print("  小米刷机助手 - 一键编译脚本 (防篡改版)")
    print("=" * 50)
    print()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"工作目录: {script_dir}")
    print()

    # 检查UPX
    upx_exe = _find_upx()
    if not upx_exe:
        print("[警告] 未找到upx.exe, 跳过UPX加壳")
    else:
        print(f"[OK] 找到UPX: {upx_exe}")
    print()

    # 清理旧文件
    print("[步骤1] 清理旧的编译文件...")
    for item in ["XiaoMiFlashTool.spec", "build", "__pycache__", "dist"]:
        path = os.path.join(script_dir, item)
        if os.path.isfile(path):
            os.remove(path)
            print(f"  删除文件: {item}")
        elif os.path.isdir(path):
            shutil.rmtree(path)
            print(f"  删除目录: {item}")
    print("清理完成！")
    print()

    print("[步骤2] 开始编译...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--noupx",
        "--name", "XiaoMiFlashTool",
        "--add-data", "tools;tools",
        "--add-data", "XiaoMi\\_wxpay_thumb.png;XiaoMi",
        "--add-data", "XiaoMi\\_alipay_thumb.png;XiaoMi",
        "--add-data", "XiaoMi\\_wxfriend_thumb.png;XiaoMi",
        "--add-data", "XiaoMi\\_qqfriend_thumb.png;XiaoMi",
        "--add-data", "XiaoMi\\微信收款.png;XiaoMi",
        "--add-data", "XiaoMi\\支付宝收款.png;XiaoMi",
        "--add-data", "XiaoMi\\微信好友.png;XiaoMi",
        "--add-data", "XiaoMi\\QQ好友.png;XiaoMi",
        "--add-data", "XiaoMi\\DisableAllFileWarnings.bat;XiaoMi",
        "--add-data", "XiaoMi\\DisableAllFileWarnings.ps1;XiaoMi",
        "--add-data", "XiaoMi\\OPPO.exe;XiaoMi",
        "--add-data", "XiaoMi\\WinMemoryCleaner.exe;XiaoMi",
        "--add-data", "XiaoMi\\Bandizipv6.29.exe;XiaoMi",
        "--exclude-module", "PIL",
        "--exclude-module", "Pillow",
        "--exclude-module", "unittest",
        "--exclude-module", "email",
        "--exclude-module", "xml",
        "--exclude-module", "pydoc",
        "flash_tool.py"
    ]
    result = subprocess.run(cmd, cwd=script_dir)
    if result.returncode != 0:
        print("[错误] 编译失败！")
        input("按回车键退出...")
        return 1

    exe_path = os.path.join(script_dir, "dist", "XiaoMiFlashTool.exe")
    if not os.path.exists(exe_path):
        print("[错误] 未找到输出文件！")
        input("按回车键退出...")
        return 1

    print()
    print("[步骤3] UPX加壳...")
    if upx_exe:
        subprocess.run([upx_exe, "--best", "--compress-icons=0", "--force", exe_path],
                       cwd=script_dir, capture_output=True)
        size_upx = os.path.getsize(exe_path) / (1024*1024)
        print(f"  UPX后大小: {size_upx:.1f} MB")
    else:
        print("  跳过UPX (未找到upx.exe)")

    print()
    print("[步骤4] 写入完整性校验码...")
    h = _append_hash(exe_path)
    print(f"  SHA256校验码: {h}")
    size_final = os.path.getsize(exe_path) / (1024*1024)
    print(f"  最终大小: {size_final:.1f} MB")

    print()
    print("[步骤5] 清理临时文件...")
    for item in ["build", "XiaoMiFlashTool.spec", "__pycache__"]:
        path = os.path.join(script_dir, item)
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.isfile(path):
            os.remove(path)
    print("清理完成！")
    print()

    print("=" * 50)
    print("  编译完成！")
    print("=" * 50)
    print()
    print(f"输出文件: {exe_path}")
    print(f"文件大小: {size_final:.1f} MB")
    if upx_exe:
        print(f"UPX: ✓ 已加壳 (破解难度提升)")
    print(f"完整性: ✓ SHA256校验码已嵌入 (防止篡改)")
    print()
    os.startfile(os.path.join(script_dir, "dist"))
    input("按回车键退出...")
    return 0

if __name__ == "__main__":
    main()