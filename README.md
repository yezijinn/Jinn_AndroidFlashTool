# 小米刷机工具 (XiaoMi Flash Tool)

一款功能强大的Windows单文件exe刷机工具，支持小米/红米等Android手机的ADB/Fastboot操作。

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
- 单文件exe，无需安装

## 使用方法

1. 下载并运行 `XiaoMiFlashTool.exe`
2. 手机开启USB调试，连接电脑
3. 根据需要选择相应功能

## 项目结构

```
flash_tool/
├── XiaoMiFlashTool.exe   # 编译后的可执行文件
├── flash_tool.py         # 主程序源码
├── 编译.py               # 编译脚本
├── tools/                # ADB/Fastboot/Scrcpy工具
├── XiaoMi/               # 内置工具和二维码图片
├── upx/                  # UPX加壳工具
└── README.md             # 本文件
```

## 从源码编译

```bash
# 安装依赖
pip install pyinstaller

# 编译
python 编译.py
```

## 开源协议

MIT License - 详见 [LICENSE](LICENSE) 文件

## 注意事项

1. 刷机有风险，请提前备份重要数据
2. BL解锁会清除手机数据
3. 请仅用于学习和研究