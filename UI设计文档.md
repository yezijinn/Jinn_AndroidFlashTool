# 小米刷机助手 UI 设计文档

> 版本: v3.1（PySide6 极光暗黑主题 + Frameless 自绘标题栏）
> 适用源码: `flash_tool.py` + `aurora_theme.py`

---

## 一、技术栈总览

| 项目 | 说明 |
|------|------|
| 编程语言 | Python 3.11 |
| GUI 框架 | PySide6 6.11 (Qt Widgets, Fusion 风格基底) |
| 窗口形态 | **Frameless（无边框）+ 自绘标题栏**，原生窗口行为经 `startSystemMove`/`startSystemResize` 代理 |
| 主题机制 | 语义化 Token + QPalette + 生成式应用级 QSS |
| 动画 | 仅限头栏 `AuroraHeader`（~11FPS，失焦自动暂停） |
| 图标 | 自绘 SVG → 多尺寸 ICO (16~256px) |
| 打包 | PyInstaller 6.x（onedir + `_internal` 隐藏依赖夹） |
| 目标平台 | Windows 8.1/10/11 64 位 |

**核心原则**：界面视觉统一由"语义别名"驱动，业务代码不散落任何十六进制色值；所有控件状态（rest/hover/pressed/focus/disabled）在应用级 QSS 内全覆盖。自绘标题栏由主题层统一管理颜色、按钮状态与窗口控制，彻底消除"OS 标题栏颜色与程序背景不一致"问题。

---

## 二、文件结构与职责

```
flash_tool/
├── flash_tool.py          # 主程序：业务逻辑 + 窗口装配 (1067行)
├── aurora_theme.py        # 主题层：Token/调色板/QSS渲染/极光头栏 (424行)
├── assets/
│   ├── app_icon.svg       # 图标矢量源文件
│   └── app_icon.ico       # 多尺寸图标 (16/24/32/48/64/128/256)
├── 编译.py                # 一键编译 (PyInstaller + 瘦身 + 图片加密 + UPX + SHA校验)
├── tools/                 # adb / fastboot / scrcpy 工具 (随包分发)
└── XiaoMi/                # 二维码图片 / 驱动 / 清理 / 压缩工具
```

| 文件 | 角色 | 关注点 |
|------|------|--------|
| `aurora_theme.py` | **外观唯一权威** | 颜色、字体、间距、状态、动画全部集中于此 |
| `flash_tool.py` | **行为唯一权威** | 命令队列、线程、adb/fastboot/scrcpy、文件传输 |
| `编译.py` | **交付流水线** | 编译、瘦身、加密、加壳、校验 |

---

## 三、主题架构（aurora_theme.py）

### 3.1 语义化 Token（极光调色板）

颜色以"用途"而非"色值"命名，业务代码只认别名：

```python
TOKENS = {
    'bg_base': '#05070d',      # 最深底
    'bg_elevated': '#0a101f',  # 表面层（标题栏/状态栏/分组框）
    'bg_card': '#0f1626',      # 卡片层
    'bg_console': '#02040a',   # 输出区（极深）
    'text_primary': '#e7eefc',
    'text_secondary': '#7e90b4',
    'teal': '#2dd4bf',         # 极光绿青
    'cyan': '#22d3ee',         # 极光青
    'indigo': '#6366f1',       # 极光靛
    'violet': '#a78bfa',       # 极光紫
    'focus': '#a78bfa',        # 键盘焦点
    'selection': '#4f46e5',    # 文本选中
    # ... 完整色板见源码
}
```

配色逻辑：**深空蓝紫底**（`bg_base`/`bg_elevated`/`bg_card` 三档表面）承载内容，**绿→青→靛→紫**极光渐变作为强调色/主按钮/头栏光晕，红/黄保留为错误/警告语义色。文字按主/次/禁用三档区分层级。

### 3.2 三层外观机制分工

| 机制 | 负责 | 例 |
|------|------|----|
| `QPalette` | 宽泛语义角色 | Window/Base/Text/Highlight/ToolTip，含 Active/Inactive/Disabled 三组 |
| 生成式应用 QSS | 组件边框/圆角/内边距/状态/子控件 | 按钮、输入框、标签页、分组框、滚动条 |
| 动态属性 | 语义变体/角色/严重度 | `fluentAppearance`、`fluentSize`、`fluentRole` |

### 3.3 生成式 QSS（单一来源）

QSS 以模板存放，含 `@{token}` 占位符，`build_qss()` 渲染时**未解析占位符直接抛错**，杜绝静默遗留：

```css
QPushButton[fluentAppearance="primary"] {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 @{brand_top}, stop:0.90 @{brand_top}, stop:0.90 @{brand_hi}, stop:1 @{brand_hi});
}
```

按钮底部"强调色细条"用 `qlineargradient` 的锐利色带实现（0.90→1.0 处颜色突变），保留原 Tkinter 版的设计 DNA。

### 3.4 动态属性词汇表

| 属性 | 取值 |
|------|------|
| `fluentAppearance` | default / primary / danger / green / cyan / outline |
| `fluentSize` | compact（小按钮自动命中） |
| `fluentRole` | title / section / muted / ok / err / consoleTitle / card / panel / divider |

### 3.5 全状态覆盖

每个可交互控件均实现：**rest / hover / pressed / focus / disabled**。键盘焦点（`:focus`）与悬停（`:hover`）完全独立，焦点边框用紫色 `focus` token，不随鼠标悬停显示。

---

## 四、窗口布局结构（flash_tool.py）

```
QMainWindow (Frameless, 1120x850, 最小 1000x750)
└─ windowFrame QWidget            # 活动/非活动外框 (1px语义边框, 最大化隐藏)
   ├─ CustomTitleBar 36px         # 自绘标题栏
   │   ├─ App图标 + 窗口标题       #   （居左）
   │   ├─ 最小化 / 最大化还原 / 关闭  # （居右, 46x36, 关闭=Windows危险红）
   ├─ centralRoot (竖向渐变底)
   │   ├─ AuroraHeader            # 极光头栏 (固定64px)
   │   │   ├─ 标题 QLabel
   │   │   ├─ 版本 QLabel
   │   │   └─ 管理员指示器 QFrame(panel)
   │   ├─ QTabWidget (stretch=4)  # 7个功能页
   │   │   ├─ 设备信息 / 刷入面具 / 刷Recovery / 文件管理
   │   │   ├─ 高级功能 / 实用工具 / 投屏控制   (均包在 QScrollArea 内)
   │   ├─ 底部 QWidget (stretch=3)
   │   │   ├─ 命令输出 QPlainTextEdit (5色日志标签)
   │   │   └─ 二维码卡片 (2x2网格, 含"大图"弹窗)
   │   └─ QStatusBar
   │       ├─ 状态 QLabel
   │       └─ 工具状态 QLabel (ADB/Fastboot 检测)
   └─ WindowResizeHandles         # 8个不可见边缘/角落缩放热区 (startSystemResize)
```

### 4.0 Frameless 自绘标题栏（CustomTitleBar）

- **窗口标志**：`FramelessWindowHint | Window`，不引入 `WA_TranslucentBackground`（纯不透明，Win11 DWM 自动圆角）
- **拖动**：标题栏左键按下后位移超过阈值即调用 `QWindow.startSystemMove()`，原生系统接管 → **Aero Snap、贴边、最大化（拖到顶部）全部由 Windows 原生处理**，不做任何手动坐标计算
- **最大化/还原**：双击标题栏或点击最大化按钮切换；`changeEvent` 同步 `windowMaximized` 属性
- **外框**：`#windowFrame` 1px 语义边框（活动=`window_border_active` 靛蓝，失活=`window_border_inactive`）；最大化时边距置 0 并隐藏边框，让内容铺满工作区（不覆盖任务栏）
- **窗口控制按钮**：`CaptionButton` 自绘符号（46x36），状态由 QSS 驱动；关闭按钮 hover/pressed 使用 Windows 危险红（`#e81123`/`#bf0f1e`）；最大化/还原按钮符号与工具提示随状态自动切换；每个按钮有 accessible name
- **缩放**：8 个不可见边缘/角落热区（6px 边 / 14px 角）委托 `QWindow.startSystemResize()`，不拦截中央区域鼠标事件
- **失活态**：`windowActive` 动态属性驱动标题栏/外框/标题文字变暗，保持可读性

### 4.1 AuroraHeader（极光光晕）

- **静态部分**：竖向深空渐变底 + 底部 2px 极光渐变线
- **动态部分**：4 个径向渐变"光晕斑点"（绿/青/靛/紫）以正弦函数极慢漂移
- **低消耗设计**：
  - 仅重绘 64px 高的头栏小区域
  - ~11FPS（90ms 间隔）
  - 窗口失焦/最小化/隐藏时 `QTimer` 自动暂停（事件过滤器监听 WindowActivate/StateChange）
  - 光晕越界处 alpha=0，无额外合成开销

---

## 五、线程与命令模型（行为层）

```
用户点击 ──► _run(tool, args) ──► 命令队列 (_cmd_queue, 加锁)
                                      │
                                      ▼ 顺序出队
                              _exec_subprocess (Popen + readline)
                                      │
                     ┌────────────────┴──────────────┐
                     │ 工作线程                        │
                     │  · 读输出 → log_signal.emit     │
                     │  · 结束   → finished_signal     │
                     └────────────────────────────────┘
                              │ (Qt 信号跨线程自动排队)
                              ▼
                     GUI线程 _log / _set_status
```

- 命令队列解决 fastboot 阻塞式等待问题，命令严格顺序执行
- 所有跨线程回写通过 `Signal(str,str)` / `Signal(object)` 完成，**不在工作线程触碰任何控件**
- 投屏 (scrcpy) 完全独立：不走队列、不占 `is_running`、输出不显示

---

## 六、打包流水线（编译.py）

| 步骤 | 内容 |
|------|------|
| 1 | 清理旧编译产物 |
| 2 | PyInstaller onedir（含 exe 图标、`--add-data` 资源、排除无用模块） |
| 3 | PySide6 瘦身：删除 QML/Quick/Pdf/OpenGL/Network/Svg 等未用 DLL 与插件（约 -40MB） |
| 4 | 二维码图片 XOR 加密为 `.enc`（SHA256 流密钥，运行时内存解密） |
| 5 | UPX 加壳 |
| 6 | SHA256 完整性校验码写入 exe 末尾 |
| 7 | `_internal` 依赖夹隐藏 |
| 8 | 清理临时文件 |

**体积**：exe 约 1.3MB，整体目录约 114MB。

---

## 七、安全与兼容

- **完整性自校验**：启动时比对 exe 末尾 SHA256，被篡改即拒绝运行（Win32 MessageBoxW 提示）
- **图片防提取**：二维码编译期加密为 `.enc`，包内无原图
- **严格内置 adb**：`get_tool_path` 只认打包内置工具，禁止回退系统 PATH
- **中文兼容**：`locale.getpreferredencoding()` 处理 GBK 系统输出；中文长路径经短路径 (8.3) 规避 cmd 乱码
- **图标**：16~256px 多尺寸 ICO，窗口图标 + exe 资源图标双通道
- **标题栏统一**：Frameless 自绘标题栏（36px），颜色/状态/按钮全部走主题 Token，与程序背景天然一致；Win8.1 等旧系统下 `startSystemMove`/`startSystemResize` 正常降级为手动拖动与缩放

---

## 八、设计规范速查

1. **别用色值，用别名** —— 颜色一律来自 `TOKENS` / `LOG_COLORS`
2. **禁止散落 `setStyleSheet()`** —— 外观统一走 `aurora_theme.apply_theme()` 的应用级 QSS
3. **每个交互控件必须有键盘焦点态** —— 焦点与悬停独立
4. **状态不能只靠颜色** —— 错误/警告配合文字或图标
5. **不用固定几何布局** —— 一律 layouts + size policies（窗口控制按钮、缩放热区除外）
6. **动画必须低消耗** —— 只在极小区域、低 FPS、失焦暂停
7. **改外观不动行为** —— 信号/队列/线程/持久化保持稳定
8. **Frameless 不重造原生行为** —— 拖动/缩放/贴靠一律委托 `startSystemMove`/`startSystemResize`

---

*本文档对应源码为 v3.0；修改主题请改 `aurora_theme.py`，修改行为请改 `flash_tool.py`。*
