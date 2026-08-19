# 小米刷机工具 (XiaoMi Flash Tool)

一款功能简洁、界面专业的 Windows 刷机工具，支持 Android 手机的 ADB/Fastboot 操作。

## 功能特性

- **设备管理**: ADB/Fastboot 设备检测、机型查询、内核版本查看
- **重启模式**: 重启到 Fastboot/Recovery/系统
- **Magisk 面具**: 刷入 Magisk/KernelSU 镜像获取 ROOT 权限
- **Recovery 刷入**: 支持多种模式刷入 TWRP 等 Recovery
- **文件管理**: ADB Push/Pull 文件传输，支持中文路径
- **投屏控制**: 使用 scrcpy 实现手机投屏与控制
- **高级功能**: BL 解锁、vbmeta 刷入、自定义命令、系统维护
- **实用工具**: 设备管理器、驱动安装、内存清理、压缩工具
- **石墨暗黑主题**: Windows Fluent Dark 风格，高对比度文字、纯色扁平控件、低占用
- **无边框窗口**: 自绘标题栏，原生移动/缩放/Snap，关闭按钮 Windows 危险色
- **安全保护**: UPX 加壳 + SHA256 完整性校验，防止篡改

## 系统要求

- Windows 8.1/10/11 64 位（不支持 Win7：Python 3.11 需要 Win8+ 系统组件）
- 无需安装任何运行库
- 目录版 exe（onedir），支持文件与 exe 同目录，免安装、无临时解压

> 注：「内存清理」工具 (WinMemoryCleaner) 依赖系统 .NET Framework 4.x（Win10/11 已内置，无需安装）；其余功能零外部依赖，全部工具随包分发。

## 使用方法

1. 下载 Release 分发包并解压，运行 `XiaoMiFlashTool.exe`。
2. 手机开启 USB 调试，连接电脑，建议使用原装数据线，台式机接主板上 (机箱背面)。
3. 电脑缺少安卓驱动时，进入「高级功能」页，点击「安装安卓驱动 (OPPO)」。

## 项目结构

```
flash_tool/
├── dist/XiaoMiFlashTool/  # 编译输出目录 (分发时整个文件夹压缩为 Release 包)
│   ├── XiaoMiFlashTool.exe  # 可执行文件 (UPX加壳+SHA校验)
│   └── _internal/           # 依赖文件夹 (默认隐藏属性)
│       ├── tools/           # ADB/Fastboot/Scrcpy工具
│       └── XiaoMi/          # 工具 + 二维码图片(加密为.enc, 包内无原图)
├── flash_tool.py         # 主程序源码 (业务逻辑)
├── aurora_theme.py       # 石墨暗黑主题层 (token/调色板/QSS/自绘标题栏)
├── UI设计文档.md          # UI 设计文档 (主题架构/布局/线程/打包)
├── assets/               # 应用图标 (app_icon.svg 源文件 + app_icon.ico 多尺寸)
├── 编译.py               # 编译脚本 (含图片加密/UPX/加校验码/隐藏依赖夹)
├── tools/                # 源码用工具 (编译时打进 exe 目录)
├── XiaoMi/               # 源码用资源
├── upx/                  # UPX加壳工具
└── README.md             # 本文件
```

## 安全与防提取

- **图片加密**: 二维码图片在编译时加密为 `.enc`（SHA256 流密钥 XOR），运行时在内存解密显示，包内不出现原图
- **防篡改**: UPX 加壳 + SHA256 完整性自校验（启动时比对 exe 末尾校验码）
- **依赖隐藏**: `_internal` 依赖文件夹默认隐藏

## 从源码编译

```bash
# 安装依赖 (需要 PySide6 + PyInstaller 6.x, 用于--contents-directory单依赖夹布局)
pip install -U pyinstaller PySide6

# 编译 (产出 dist/XiaoMiFlashTool/ 完整目录)
python 编译.py
```

## 发布 Release

```bash
# 将 dist/XiaoMiFlashTool/ 压缩为 zip 并上传到 GitHub Release
# 编译脚本已自动完成图片加密/UPX/校验码写入
gh release create v3.0 dist/XiaoMiFlashTool.zip --title "v3.0" --notes "..."
```

## 开源协议

MIT License - 详见 [LICENSE](LICENSE) 文件

## 注意事项

1. 刷机有风险，请提前备份重要数据
2. BL 解锁会清除手机数据
3. 请仅用于学习和研究