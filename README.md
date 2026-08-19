# 小米刷机工具 (XiaoMi Flash Tool)

一款功能简单、画面简约的Windows刷机工具，支持Android手机的ADB/Fastboot操作。

## 功能特性

- **设备管理**: ADB/Fastboot设备检测、机型查询、内核版本查看
- **重启模式**: 重启到Fastboot/Recovery/系统
- **Magisk面具**: 刷入Magisk/KernelSU镜像获取ROOT权限
- **Recovery刷入**: 支持多种模式刷入TWRP等Recovery
- **文件管理**: ADB Push/Pull文件传输，支持中文路径
- **投屏控制**: 使用scrcpy实现手机投屏与控制
- **实用工具**: 设备管理器、驱动安装、内存清理、压缩工具
- **安全保护**: UPX加壳 + SHA256完整性校验，防止篡改

## 系统要求

- Windows 7/8/10/11 64位
- 无需安装任何运行库
- 目录版exe（onedir），支持文件与exe同目录，免安装、无临时解压

## 使用方法

1. 下载并运行 `XiaoMiFlashTool.exe`。
2. 手机开启USB调试，连接电脑，建议使用原装数据线，台式机接主板上(机箱背面)。
3. 电脑缺少安卓驱动时，点击菜单“实用工具”，点击按钮“安卓的驱动”。

## 项目结构

```
flash_tool/
├── dist/XiaoMiFlashTool/  # 编译输出目录 (分发时整个文件夹拷走)
│   ├── XiaoMiFlashTool.exe  # 可执行文件 (UPX加壳+SHA校验)
│   └── _internal/           # 依赖文件夹 (默认隐藏属性)
│       ├── tools/           # ADB/Fastboot/Scrcpy工具
│       └── XiaoMi/          # 工具 + 二维码图片(加密为.enc, 包内无原图)
├── flash_tool.py         # 主程序源码
├── 编译.py               # 编译脚本 (含图片加密/UPX/加校验码/隐藏依赖夹)
├── tools/                # 源码用工具 (编译时打进exe目录)
├── XiaoMi/               # 源码用资源
├── upx/                  # UPX加壳工具
└── README.md             # 本文件
```

## 安全与防提取

- **图片加密**: 二维码图片在编译时加密为 `.enc`（SHA256流密钥XOR），运行时在内存解密显示，包内不出现原图
- **防篡改**: UPX加壳 + SHA256完整性自校验（启动时比对exe末尾校验码）
- **依赖隐藏**: `_internal` 依赖文件夹默认隐藏

## 从源码编译

```bash
# 安装依赖 (需要 PyInstaller 6.x, 用于--contents-directory单依赖夹布局)
pip install -U pyinstaller

# 编译
python 编译.py
```

## 开源协议

MIT License - 详见 [LICENSE](LICENSE) 文件

## 注意事项

1. 刷机有风险，请提前备份重要数据
2. BL解锁会清除手机数据
3. 请仅用于学习和研究