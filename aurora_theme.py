# -*- coding: utf-8 -*-
"""
石墨暗黑主题层 - Graphite Dark Theme (Windows Fluent Dark 风格)
语义化 token + QPalette + 生成式 QSS + 静态头栏
应用只消费语义别名, 不散落十六进制颜色

设计原则: 文字对比度 > 信息层级 > 控件状态 > 装饰效果
无渐变、无霓虹光晕、细边框、4~6px 小圆角
"""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (QColor, QPainter, QFont, QPalette, QPen)
from PySide6.QtWidgets import QWidget, QLabel, QAbstractButton, QHBoxLayout

# ── 语义化 Token (中性石墨黑 + 低饱和蓝 accent) ──
TOKENS = {
    # 表面
    'bg_base':       '#111111',   # 主背景
    'bg_gradient_hi': '#111111',  # 兼容键 (无渐变, 与主背景一致)
    'bg_gradient_lo': '#111111',
    'bg_elevated':   '#181818',   # 表面层 (标题/状态栏/分组框)
    'bg_card':       '#202020',   # 卡片层
    'bg_overlay':    '#2A2A2A',   # 悬停层
    'bg_pressed':    '#333333',   # 按压层
    'bg_console':    '#0C0C0C',   # 输出区 (极深)
    'bg_input':      '#181818',   # 输入框
    # 边框
    'border':        '#353535',
    'border_strong': '#454545',
    'divider':       '#2A2A2A',
    # 文字
    'text_primary':   '#F5F5F5',
    'text_secondary': '#C5C5C5',
    'text_muted':     '#8F8F8F',
    'text_disabled':  '#666666',
    'text_on_brand':  '#0F1115',
    # 强调色 (低饱和蓝)
    'accent':     '#4CC2FF',
    'accent_hi':  '#66CCFF',
    'accent_dim': '#2B8BC9',
    # 兼容旧键名 (统一映射到新语义)
    'teal':   '#4CC2FF',
    'teal_hi':'#66CCFF',
    'cyan':   '#4CC2FF',
    'cyan_hi':'#66CCFF',
    'indigo': '#4CC2FF',
    'indigo_hi':'#66CCFF',
    'violet': '#4CC2FF',
    # 状态色
    'green':   '#4CC38A',
    'green_hi':'#6ED8A5',
    'red':     '#F06A6A',
    'red_hi':  '#F88B8B',
    'yellow':  '#E8B04A',
    'yellow_hi':'#F0C060',
    'pink':    '#E8B04A',
    # 语义状态
    'success': '#4CC38A',
    'warning': '#E8B04A',
    'danger':  '#F06A6A',
    # 品牌 (纯色, 无渐变)
    'brand_top': '#4CC2FF',
    'brand_bot': '#4CC2FF',
    'brand_hi':  '#66CCFF',
    # 状态
    'focus': '#66CCFF',
    'selection': '#2D5A80',
    'selection_text': '#FFFFFF',
    'tooltip_bg': '#202020',
    # 标题栏 (frameless)
    'titlebar_bg':          '#181818',
    'titlebar_bg_inactive': '#141414',
    'titlebar_text':        '#F5F5F5',
    'titlebar_text_inactive': '#C5C5C5',
    'titlebar_hover':       '#2A2A2A',
    'titlebar_pressed':     '#333333',
    'titlebar_close_hover': '#F06A6A',
    'titlebar_close_pressed': '#C04040',
    'window_border_active':   '#454545',
    'window_border_inactive': '#2A2A2A',
}

# 日志标签 → 颜色
LOG_COLORS = {
    'cmd':  TOKENS['accent'],
    'ok':   TOKENS['success'],
    'warn': TOKENS['warning'],
    'err':  TOKENS['danger'],
    'info': TOKENS['text_primary'],
}

# ── QPalette (宽泛语义角色) ──
def build_palette():
    T = TOKENS
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(T['bg_base']))
    pal.setColor(QPalette.WindowText, QColor(T['text_primary']))
    pal.setColor(QPalette.Base, QColor(T['bg_input']))
    pal.setColor(QPalette.AlternateBase, QColor(T['bg_elevated']))
    pal.setColor(QPalette.Text, QColor(T['text_primary']))
    pal.setColor(QPalette.PlaceholderText, QColor(T['text_muted']))
    pal.setColor(QPalette.Button, QColor(T['bg_card']))
    pal.setColor(QPalette.ButtonText, QColor(T['text_primary']))
    pal.setColor(QPalette.Highlight, QColor(T['selection']))
    pal.setColor(QPalette.HighlightedText, QColor(T['selection_text']))
    pal.setColor(QPalette.Link, QColor(T['accent']))
    pal.setColor(QPalette.LinkVisited, QColor(T['accent']))
    pal.setColor(QPalette.ToolTipBase, QColor(T['tooltip_bg']))
    pal.setColor(QPalette.ToolTipText, QColor(T['text_primary']))
    # Inactive / Disabled
    for group in (QPalette.Inactive, QPalette.Disabled):
        pal.setColor(group, QPalette.WindowText, QColor(T['text_disabled']))
        pal.setColor(group, QPalette.Text, QColor(T['text_disabled']))
        pal.setColor(group, QPalette.ButtonText, QColor(T['text_disabled']))
        pal.setColor(group, QPalette.Highlight, QColor(T['text_disabled']))
        pal.setColor(group, QPalette.HighlightedText, QColor(T['text_primary']))
    return pal

# ── 生成式应用 QSS (单一来源, 含完整状态覆盖) ──
_QSS = r"""
QWidget { font-family: 'Microsoft YaHei UI'; font-size: 14px; color: @{text_primary}; }
QMainWindow, QDialog { background: @{bg_base}; }

#centralRoot { background: @{bg_base}; }

/* 标签页 */
QTabWidget::pane { border: 1px solid @{border}; border-radius: 6px;
    background: @{bg_card}; top: -1px; }
QTabWidget { background: transparent; }
QTabBar::tab { background: transparent; color: @{text_secondary};
    padding: 9px 20px; margin-right: 4px; border: none;
    border-top-left-radius: 6px; border-top-right-radius: 6px; font-weight: bold; }
QTabBar::tab:hover { background: @{bg_overlay}; color: @{text_primary}; }
QTabBar::tab:selected { background: @{bg_card}; color: @{text_primary};
    border-bottom: 2px solid @{accent}; }
QTabBar::tab:disabled { color: @{text_disabled}; }

/* 分组框 */
QGroupBox { background: @{bg_elevated}; border: 1px solid @{border};
    border-radius: 6px; margin-top: 12px; padding: 8px 4px 4px 4px;
    font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 14px; top: 0px;
    color: @{accent}; padding: 0 6px; }

/* 普通标签 */
QLabel { background: transparent; }

/* 语义标签角色 */
QLabel[fluentRole="title"] { color: @{text_primary}; font-size: 18px; font-weight: bold; }
QLabel[fluentRole="section"] { color: @{accent}; font-weight: bold; }
QLabel[fluentRole="muted"] { color: @{text_muted}; font-size: 13px; }
QLabel[fluentRole="ok"] { color: @{success}; }
QLabel[fluentRole="err"] { color: @{danger}; }
QLabel[fluentRole="consoleTitle"] { color: @{accent}; font-weight: bold; }

/* 容器角色 (卡片/面板/分隔条) */
QFrame[fluentRole="card"] { background: @{bg_card}; border: 1px solid @{border}; border-radius: 6px; }
QFrame[fluentRole="panel"] { background: @{bg_elevated}; border: 1px solid @{border}; border-radius: 6px; }
QFrame[fluentRole="divider"] { background: @{divider}; border: none; }

/* 按钮: 全状态覆盖 (rest/hover/pressed/focus/disabled) — 纯色扁平 */
QPushButton {
    color: @{text_primary};
    border: 1px solid @{border};
    border-radius: 6px;
    padding: 5px 14px;
    background: @{bg_card};
}
QPushButton:hover { background: @{bg_overlay}; border-color: @{border_strong}; color: @{text_primary}; }
QPushButton:pressed { background: @{bg_pressed}; border-color: @{border_strong}; }
QPushButton:disabled { color: @{text_disabled}; background: @{bg_elevated}; border-color: @{divider}; }
QPushButton:focus { border: 1px solid @{focus}; }

QPushButton[fluentAppearance="primary"] {
    color: @{text_on_brand};
    border-color: transparent;
    background: @{accent};
}
QPushButton[fluentAppearance="primary"]:hover { background: @{accent_hi}; color: #0F1115; }
QPushButton[fluentAppearance="primary"]:pressed { background: @{accent_dim}; color: #FFFFFF; }

QPushButton[fluentAppearance="danger"] {
    color: #FFFFFF;
    border-color: transparent;
    background: @{danger};
}
QPushButton[fluentAppearance="danger"]:hover { background: @{red_hi}; }
QPushButton[fluentAppearance="danger"]:pressed { background: #C04040; color: #FFFFFF; }

QPushButton[fluentAppearance="green"] {
    color: #0F1115;
    border-color: transparent;
    background: @{success};
}
QPushButton[fluentAppearance="green"]:hover { background: @{green_hi}; }
QPushButton[fluentAppearance="green"]:pressed { background: #35885F; color: #FFFFFF; }

QPushButton[fluentAppearance="cyan"] {
    color: @{text_on_brand};
    border-color: transparent;
    background: @{accent};
}
QPushButton[fluentAppearance="cyan"]:hover { background: @{accent_hi}; }
QPushButton[fluentAppearance="cyan"]:pressed { background: @{accent_dim}; color: #FFFFFF; }

QPushButton[fluentAppearance="outline"] {
    color: @{accent};
    border-color: @{border_strong};
    background: transparent;
}
QPushButton[fluentAppearance="outline"]:hover { background: @{bg_overlay}; border-color: @{accent}; }
QPushButton[fluentAppearance="outline"]:pressed { background: @{bg_pressed}; color: @{accent_hi}; }

QPushButton[fluentSize="compact"] { padding: 3px 10px; font-size: 12px; border-radius: 4px; }

/* ── 自绘标题栏 (frameless) ── */
QWidget[fluentRole="titleBar"] {
    background: @{titlebar_bg};
    border-bottom: 1px solid @{divider};
}
QWidget[fluentRole="titleBar"][windowActive="false"] {
    background: @{titlebar_bg_inactive};
}
QLabel[fluentRole="windowTitle"] {
    color: @{titlebar_text};
    font-weight: bold;
    background: transparent;
}
QLabel[fluentRole="windowTitle"][windowActive="false"] { color: @{titlebar_text_inactive}; }

/* 窗口控制按钮 (46x36) */
QWidget[fluentRole="captionButton"] { background: transparent; border: none; }
QWidget[fluentRole="captionButton"]:hover { background: @{titlebar_hover}; }
QWidget[fluentRole="captionButton"]:pressed { background: @{titlebar_pressed}; }
QWidget[fluentRole="captionButton"][captionKind="close"]:hover { background: @{titlebar_close_hover}; }
QWidget[fluentRole="captionButton"][captionKind="close"]:pressed { background: @{titlebar_close_pressed}; }

/* ── 无边框窗口外框 (活动/非活动) ── */
#windowFrame {
    border: 1px solid @{window_border_active};
    background: @{bg_base};
}
#windowFrame[windowActive="false"] { border-color: @{window_border_inactive}; }
#windowFrame[windowMaximized="true"] { border: none; }

/* 输入框: rest/hover/focus/disabled/read-only/invalid */
QLineEdit { background: @{bg_input}; color: @{text_primary};
    border: 1px solid @{border}; border-radius: 4px; padding: 6px 10px;
    selection-background-color: @{selection}; selection-color: @{selection_text};
    min-height: 18px; }
QLineEdit:hover { border-color: @{border_strong}; }
QLineEdit:focus { border: 1px solid @{focus}; background: @{bg_card}; }
QLineEdit:disabled { color: @{text_disabled}; background: @{bg_elevated}; border-color: @{divider}; }
QLineEdit:read-only { color: @{text_secondary}; background: @{bg_elevated}; }
QLineEdit[fluentInvalid="true"] { border-color: @{danger}; }

/* 输出控制台 */
QPlainTextEdit { background: @{bg_console}; color: @{text_primary};
    border: 1px solid @{border}; border-radius: 4px; padding: 8px;
    selection-background-color: @{selection}; selection-color: @{selection_text}; }

/* 滚动条 (窄) */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: @{border_strong}; border-radius: 4px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: @{accent}; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: @{border_strong}; border-radius: 4px; min-width: 28px; }
QScrollBar::handle:horizontal:hover { background: @{accent}; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

/* 滚动区域透明化 (露出标签页卡片底色) */
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }

/* 单选 / 复选 — 圆形指示器 (未勾=空心圆, 已勾=绿色实心圆) */
QRadioButton, QCheckBox { color: @{text_primary}; spacing: 8px;
    padding: 4px 2px; background: transparent; }
QRadioButton:hover, QCheckBox:hover { color: @{text_primary}; }
QRadioButton::indicator, QCheckBox::indicator { width: 16px; height: 16px;
    border: 1px solid @{border_strong}; background: @{bg_input}; border-radius: 9px; }
QRadioButton::indicator:hover, QCheckBox::indicator:hover { border-color: @{accent}; }
QRadioButton::indicator:checked { background: @{success}; border: 1px solid @{success};
    border-radius: 9px; }
QCheckBox::indicator:checked { background: @{success}; border: 1px solid @{success};
    border-radius: 9px; }
QRadioButton::indicator:disabled, QCheckBox::indicator:disabled {
    background: @{bg_elevated}; border-color: @{divider}; }
QRadioButton:disabled, QCheckBox:disabled { color: @{text_disabled}; }

/* 分隔线 */
QFrame[frameShape="4"] { color: @{divider}; }

/* 分割器 */
QSplitter::handle { background: @{divider}; }
QSplitter::handle:horizontal { width: 2px; }
QSplitter::handle:vertical { height: 2px; }

/* 状态栏 */
QStatusBar { background: @{bg_elevated}; border-top: 1px solid @{border};
    min-height: 26px; }
QStatusBar QLabel { color: @{text_secondary}; padding: 2px 12px;
    background: transparent; border: none; }
QStatusBar QLabel[fluentRole="statusItem"] { color: @{text_primary};
    font-weight: bold; }

/* 菜单 / 工具提示 / 对话框按钮 */
QMenu { background: @{bg_card}; color: @{text_primary};
    border: 1px solid @{border}; border-radius: 4px; padding: 4px; }
QMenu::item { padding: 6px 22px; border-radius: 4px; }
QMenu::item:selected { background: @{bg_overlay}; }
QMenu::separator { height: 1px; background: @{divider}; margin: 4px 8px; }
QToolTip { background: @{tooltip_bg}; color: @{text_primary};
    border: 1px solid @{border_strong}; border-radius: 4px; padding: 4px 8px; }
QMessageBox QLabel { color: @{text_primary}; }
QMessageBox QPushButton { min-width: 84px; }
"""

def build_qss(tokens=None):
    """渲染应用 QSS, 未替换的占位符直接抛错 (不允许静默遗留)"""
    tokens = tokens or TOKENS
    qss = _QSS
    import re
    missing = set(re.findall(r'@\{([^}]+)\}', qss))
    if missing:
        bad = missing - set(tokens)
        if bad:
            raise KeyError(f'未解析的 token: {sorted(bad)}')
    for k, v in tokens.items():
        qss = qss.replace(f'@{{{k}}}', v)
    return qss

# ── 动态属性工具 ──
def set_prop(widget, name, value):
    """设置语义化动态属性并重绘 (不整表 repolish)"""
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()

def apply_theme(app):
    """一次应用: 字体 + 样式基底 + 调色板 + 生成式 QSS"""
    app.setFont(QFont('Microsoft YaHei UI', 10))
    app.setPalette(build_palette())
    app.setStyleSheet(build_qss())

# ══════════════════════════════════════════════════════════
# StaticHeader: 静态石墨头栏 (无动画, 零CPU开销)
#  - 纯色表面 + 底部 2px 低饱和蓝强调线
# ══════════════════════════════════════════════════════════
class AuroraHeader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(64)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

    def paintEvent(self, ev):
        p = QPainter(self)
        r = self.rect()
        w, h = r.width(), r.height()
        if w < 4 or h < 4:
            return
        p.fillRect(r, QColor(TOKENS['bg_elevated']))
        p.fillRect(0, h - 2, w, 2, QColor(TOKENS['accent']))
        p.end()


# ══════════════════════════════════════════════════════════
# Frameless 标题栏组件
#  - CustomTitleBar: 自绘标题栏 (36px), 图标+标题+窗口控制按钮
#  - CaptionButton: 最小化/最大化/关闭 (46x36, QSS 状态, 关闭=Windows危险色)
#  - 拖动走 QWindow.startSystemMove(), 原生 Snap/贴靠交给系统
# ══════════════════════════════════════════════════════════
class CaptionButton(QAbstractButton):
    """窗口控制按钮 (自绘符号, 背景状态由 QSS 驱动)"""
    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self._kind = kind  # 'min' / 'max' / 'close'
        self.setFixedSize(46, 36)
        self.setProperty("fluentRole", "captionButton")
        self.setProperty("captionKind", kind)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        tips = {'min': '最小化', 'max': '最大化', 'restore': '还原', 'close': '关闭'}
        self._tips = tips
        self._update_a11y()

    def _update_a11y(self):
        tip = self._tips.get(self._kind, '')
        self.setToolTip(tip)
        self.setAccessibleName(tip)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        p.setPen(QPen(QColor(TOKENS['titlebar_text']), 1.4))
        if self._kind == 'min':
            p.drawLine(QPointF(cx - 7, cy + 4), QPointF(cx + 7, cy + 4))
        elif self._kind == 'close':
            p.drawLine(QPointF(cx - 6, cy - 5), QPointF(cx + 6, cy + 5))
            p.drawLine(QPointF(cx - 6, cy + 5), QPointF(cx + 6, cy - 5))
        else:  # max / restore
            if self._kind == 'restore':
                p.drawRect(QRectF(cx - 8, cy - 2, 11, 11))
                p.drawRect(QRectF(cx - 3, cy - 7, 11, 11))
            else:
                p.drawRect(QRectF(cx - 7, cy - 5, 14, 10))
        p.end()


class CustomTitleBar(QWidget):
    """自绘标题栏: 图标+标题 居左, 最小化/最大化/关闭 居右
    拖动: startSystemMove(); 双击切换最大化/还原; 焦点/失焦自动切换 windowActive"""
    def __init__(self, icon_path=None, title='', parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setProperty("fluentRole", "titleBar")
        self.setProperty("windowActive", True)
        self.setObjectName("titleBarWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 0, 0)
        lay.setSpacing(8)

        if icon_path:
            icon = QLabel(self)
            icon.setPixmap(icon_path.pixmap(18, 18) if hasattr(icon_path, 'pixmap') else None)
            lay.addWidget(icon)
        if title:
            lbl = QLabel(title, self)
            lbl.setProperty("fluentRole", "windowTitle")
            lay.addWidget(lbl)
        lay.addStretch(1)

        self.btn_min = CaptionButton('min', self)
        self.btn_max = CaptionButton('max', self)
        self.btn_close = CaptionButton('close', self)
        lay.addWidget(self.btn_min)
        lay.addWidget(self.btn_max)
        lay.addWidget(self.btn_close)

        self.btn_min.clicked.connect(self._minimize)
        self.btn_max.clicked.connect(self._toggle_max)
        self.btn_close.clicked.connect(self._close)
        self._win = None
        self._drag_pos = None

    def _attach_window(self, win):
        self._win = win

    def _minimize(self):
        if self._win: self._win.showMinimized()

    def _toggle_max(self):
        if self._win:
            if self._win.isMaximized(): self._win.showNormal()
            else: self._win.showMaximized()

    def _close(self):
        if self._win: self._win.close()

    def sync_max_state(self):
        """最大化/还原时切换按钮符号与提示"""
        if not self._win: return
        maximized = self._win.isMaximized()
        kind = 'restore' if maximized else 'max'
        if self.btn_max._kind != kind:
            self.btn_max._kind = kind
            self.btn_max._update_a11y()
            self.btn_max.update()

    def sync_active(self):
        """窗口激活状态 → windowActive 动态属性 (QSS 变色)"""
        active = self._win.isActiveWindow() if self._win else True
        if self.property("windowActive") != active:
            self.setProperty("windowActive", active)
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()

    # ── 拖动 (原生 startSystemMove, 保留 Win11 Snap) ──
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if self._drag_pos is None: return
        if (e.buttons() & Qt.LeftButton):
            wh = self.window().windowHandle()
            if wh and (e.globalPosition().toPoint() - self._drag_pos).manhattanLength() > 4:
                self._drag_pos = None
                wh.startSystemMove()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._toggle_max()


# ══════════════════════════════════════════════════════════
# 无边框窗口边缘/角落缩放热区 (不可见, 委托 QWindow.startSystemResize)
# 8个热区是窗口外框的直接子控件, 不拦截窗口中央的鼠标事件
# ══════════════════════════════════════════════════════════
class WindowResizeHandles:
    """在窗口外框 (windowFrame) 四周创建 8 个原生缩放热区"""
    def __init__(self, frame):
        self._frame = frame
        self._handles = {}
        edges = {
            'n': Qt.Edge.TopEdge, 's': Qt.Edge.BottomEdge,
            'e': Qt.Edge.RightEdge, 'w': Qt.Edge.LeftEdge,
        }
        for name, edge in edges.items():
            self._handles[name] = _ResizeHandle(edge, frame)
        corners = {
            'nw': Qt.Edge.TopEdge | Qt.Edge.LeftEdge,
            'ne': Qt.Edge.TopEdge | Qt.Edge.RightEdge,
            'sw': Qt.Edge.BottomEdge | Qt.Edge.LeftEdge,
            'se': Qt.Edge.BottomEdge | Qt.Edge.RightEdge,
        }
        for name, edge in corners.items():
            self._handles[name] = _ResizeHandle(edge, frame)
        self.relayout()

    def relayout(self):
        """按当前外框尺寸摆放 8 个热区 (边缘6px, 角14px)"""
        w = self._frame.width()
        h = self._frame.height()
        s, c = 6, 14
        geo = {
            'n': (0, 0, w, s), 's': (0, h - s, w, s),
            'e': (w - s, 0, s, h), 'w': (0, 0, s, h),
            'nw': (0, 0, c, c), 'ne': (w - c, 0, c, c),
            'sw': (0, h - c, c, c), 'se': (w - c, h - c, c, c),
        }
        for name, (x, y, hw, hh) in geo.items():
            self._handles[name].setGeometry(x, y, hw, hh)
            self._handles[name].raise_()

    def setVisible(self, visible):
        for h in self._handles.values():
            h.setVisible(visible)

    def cursor_at(self, pos):
        """供窗口级鼠标事件判断是否处于边缘缩放区 (可选)"""
        return None


class _ResizeHandle(QWidget):
    """单边/单角缩放热区, 按下时调用原生 startSystemResize"""
    def __init__(self, edge, parent=None):
        super().__init__(parent)
        self._edge = edge
        # edge 可能是单值 Edge 或组合位掩码, 统一取 .value 转 int 判断方向
        def b(e):
            return int(getattr(e, 'value', e))
        bits = b(edge)
        top = bits & b(Qt.Edge.TopEdge)
        bot = bits & b(Qt.Edge.BottomEdge)
        left = bits & b(Qt.Edge.LeftEdge)
        right = bits & b(Qt.Edge.RightEdge)
        if (top and left) or (bot and right): cur = Qt.SizeFDiagCursor
        elif (top and right) or (bot and left): cur = Qt.SizeBDiagCursor
        elif top or bot: cur = Qt.SizeVerCursor
        elif left or right: cur = Qt.SizeHorCursor
        else: cur = Qt.SizeAllCursor
        self.setCursor(cur)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            wh = self.window().windowHandle()
            if wh: wh.startSystemResize(self._edge)
