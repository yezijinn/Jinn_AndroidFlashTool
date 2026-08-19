#!/usr/bin/env python3
"""小米刷机助手 - 一键编译脚本 (含UPX加壳 + 完整性校验)"""

import os
import sys
import shutil
import subprocess
import hashlib
import base64

UPX_DIR = os.path.join(os.path.dirname(__file__), 'upx')

# ── 内置图片加密 (与 flash_tool.py 保持一致) ──
_IMG_KEY = b'XiaoMiFlashTool#2026#QR-Enc'
_IMG_ENC_SUFFIX = '.enc'
BUNDLED_IMAGES = [
    '_wxpay_thumb.png', '_alipay_thumb.png', '_wxfriend_thumb.png', '_qqfriend_thumb.png',
    '微信收款.png', '支付宝收款.png', '微信好友.png', 'QQ好友.png',
]

def _img_stream(key, salt, length):
    out = bytearray(); counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(key + salt + counter.to_bytes(4, 'little')).digest())
        counter += 1
    return bytes(out[:length])

def img_xor(data, name):
    key = _img_stream(_IMG_KEY, name.encode('utf-8'), len(data))
    return bytes(a ^ b for a, b in zip(data, key))

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
        "--onedir",
        "--contents-directory", "_internal",
        "--windowed",
        "--noupx",
        "--name", "XiaoMiFlashTool",
        "--icon", "assets\\app_icon.ico",
        "--add-data", "tools;tools",
        "--add-data", "assets\\app_icon.ico;assets",
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
    ]
    # PySide6 裁剪: 只保留 Widgets/Gui/Core, 排除用不到的 Qt 模块 (体积瘦身)
    QT_EXCLUDES = [
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
        "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
        "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput",
        "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
        "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
        "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtXml",
        "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtSvg", "PySide6.QtSvgWidgets",
        "PySide6.QtUiTools", "PySide6.QtDesigner", "PySide6.QtHelp",
        "PySide6.QtNetwork", "PySide6.QtNetworkAuth",
        "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtStateMachine",
        "PySide6.QtTextToSpeech", "PySide6.QtSerialPort",
        "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning",
        "PySide6.QtLocation", "PySide6.QtSensors",
        "PySide6.QtWebSockets", "PySide6.QtWebChannel",
        "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
        "PySide6.QtOpenGLFunctions", "PySide6.QtGuiTools",
    ]
    for m in QT_EXCLUDES:
        cmd += ["--exclude-module", m]
    cmd.append("flash_tool.py")
    result = subprocess.run(cmd, cwd=script_dir)
    if result.returncode != 0:
        print("[错误] 编译失败！")
        input("按回车键退出...")
        return 1

    app_dir = os.path.join(script_dir, "dist", "XiaoMiFlashTool")
    exe_path = os.path.join(app_dir, "XiaoMiFlashTool.exe")
    if not os.path.exists(exe_path):
        print("[错误] 未找到输出文件！")
        input("按回车键退出...")
        return 1

    print()
    print("[步骤3] PySide6瘦身 (删除未使用Qt模块/插件)...")
    pyside_dir = os.path.join(app_dir, "_internal", "PySide6")
    if os.path.isdir(pyside_dir):
        removed_dlls = [
            "Qt6Quick.dll", "Qt6Qml.dll", "Qt6QmlModels.dll", "Qt6QmlMeta.dll",
            "Qt6QmlWorkerScript.dll", "Qt6Pdf.dll", "Qt6OpenGL.dll",
            "Qt6Network.dll", "Qt6Svg.dll", "Qt6VirtualKeyboard.dll",
            "opengl32sw.dll",
        ]
        for dll in removed_dlls:
            p = os.path.join(pyside_dir, dll)
            if os.path.isfile(p):
                os.remove(p); print(f"  删除: {dll}")
        plugins_dir = os.path.join(pyside_dir, "plugins")
        for sub in ["generic", "platforminputcontexts"]:
            d = os.path.join(plugins_dir, sub)
            if os.path.isdir(d):
                for f in os.listdir(d):
                    p = os.path.join(d, f)
                    if os.path.isfile(p): os.remove(p)
                os.rmdir(d); print(f"  删除插件目录: {sub}")
        rm_plugins = [
            ("iconengines", "qsvgicon.dll"),
            ("platforms", "qdirect2d.dll"),
            ("platforms", "qminimal.dll"),
            ("platforms", "qoffscreen.dll"),
            ("imageformats", "qgif.dll"), ("imageformats", "qicns.dll"),
            ("imageformats", "qpdf.dll"), ("imageformats", "qsvg.dll"),
            ("imageformats", "qtga.dll"), ("imageformats", "qtiff.dll"),
            ("imageformats", "qwbmp.dll"), ("imageformats", "qwebp.dll"),
        ]
        for sub, f in rm_plugins:
            p = os.path.join(plugins_dir, sub, f)
            if os.path.isfile(p):
                os.remove(p); print(f"  删除插件: {f}")
        print("  PySide6瘦身完成")
    else:
        print("  [警告] 未找到PySide6目录")

    print()
    print("[步骤4] 加密内置图片 (写入.enc, 删除原图)...")
    img_dir = os.path.join(app_dir, "_internal", "XiaoMi")
    if os.path.isdir(img_dir):
        n = 0
        for fn in BUNDLED_IMAGES:
            src = os.path.join(img_dir, fn)
            if not os.path.isfile(src):
                print(f"  [跳过] 不存在: {fn}")
                continue
            with open(src, 'rb') as f: data = f.read()
            with open(src + _IMG_ENC_SUFFIX, 'wb') as f: f.write(img_xor(data, fn))
            os.remove(src)
            n += 1
            print(f"  已加密: {fn}")
        print(f"图片加密完成: {n} 张")
    else:
        print(f"  [警告] 未找到内置图片目录: {img_dir}")

    print()
    print("[步骤5] UPX加壳...")
    if upx_exe:
        subprocess.run([upx_exe, "--best", "--compress-icons=0", "--force", exe_path],
                       cwd=script_dir, capture_output=True)
        size_upx = os.path.getsize(exe_path) / (1024*1024)
        print(f"  UPX后大小: {size_upx:.1f} MB")
    else:
        print("  跳过UPX (未找到upx.exe)")

    print()
    print("[步骤6] 写入完整性校验码...")
    h = _append_hash(exe_path)
    print(f"  SHA256校验码: {h}")
    size_final = os.path.getsize(exe_path) / (1024*1024)
    print(f"  最终大小: {size_final:.1f} MB")

    print()
    print("[步骤7] 隐藏依赖文件夹 (_internal)...")
    internal_dir = os.path.join(app_dir, "_internal")
    if os.path.isdir(internal_dir):
        subprocess.run(["attrib", "+h", internal_dir], capture_output=True)
        print("  已设置隐藏属性")
    else:
        print("  [警告] 未找到依赖文件夹")

    print()
    print("[步骤8] 清理临时文件...")
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
    print(f"结构: exe + _internal (隐藏依赖文件夹)")
    if upx_exe:
        print(f"UPX: OK 已加壳 (破解难度提升)")
        print(f"完整性: OK SHA256校验码已嵌入 (防止篡改)")
    print(f"图片: OK 已加密为 .enc (包内不显示原图)")
    print()
    os.startfile(os.path.join(script_dir, "dist"))
    input("按回车键退出...")
    return 0

if __name__ == "__main__":
    main()