# -*- coding: utf-8 -*-
"""
小米刷机助手 - XiaoMi Flash Tool v3.0
PySide6 极光暗黑主题版 (原 Tkinter 迁移)
单exe目录版, Win8.1-11 64位, 零外部依赖 (内置工具均随包分发)
"""
import os, sys, subprocess, threading, ctypes, locale, shlex, hashlib, base64
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QEvent, Signal
from PySide6.QtGui import QFont, QPixmap, QColor, QTextCharFormat, QTextCursor, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QLineEdit,
    QPlainTextEdit, QFrame, QGroupBox, QRadioButton, QCheckBox, QButtonGroup,
    QTabWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFileDialog, QMessageBox, QDialog, QStatusBar, QSizePolicy,
)

from aurora_theme import (LOG_COLORS, apply_theme, AuroraHeader, CustomTitleBar,
                          WindowResizeHandles)

# ── 抑制系统弹窗 (PyInstaller临时目录清理失败弹窗等) ──
try: ctypes.windll.kernel32.SetErrorMode(0x0002)  # SEM_NOOPENFILEERRORBOX
except: pass

# ── 运行时自校验 ──
def _verify_integrity():
    """校验exe自身完整性 (SHA256校验码追加在文件末尾)"""
    try:
        exe = sys.argv[0]
        if not exe.endswith('.exe'): return True  # 非打包环境跳过
        with open(exe, 'rb') as f:
            data = f.read()
        if len(data) < 64: return True
        stored = data[-44:].decode('ascii', errors='ignore').strip()
        if len(stored) != 44: return True  # 无校验码则跳过
        actual = base64.b64encode(hashlib.sha256(data[:-44]).digest()).decode()
        if actual != stored:
            ctypes.windll.user32.MessageBoxW(0, "程序已被篡改或损坏！\n请从官方渠道重新下载。",
                                             "完整性校验失败", 0x10)
            return False
    except: pass
    return True
if not _verify_integrity():
    sys.exit(1)

# ── 路径 (pathlib.Path + Unicode, 全项目统一) ──
if hasattr(sys, 'frozen'):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

# PyInstaller 内置资源目录 (onedir: exe同目录; onefile: _MEIPASS临时解压)
# 业务文件路径一律用 BASE_DIR, 不要依赖 _MEIPASS
BUNDLE_DIR = Path(getattr(sys, '_MEIPASS', BASE_DIR))

SYS_ENCODING = locale.getpreferredencoding() or 'gbk'
TOOLS_DIR = BASE_DIR / 'tools'
XIAOMI_DIR = BASE_DIR / 'XiaoMi'

def resource_path(rp):
    """PyInstaller 内置资源 (tools/下的工具), 返回Path"""
    return BUNDLE_DIR / 'tools' / rp

def xiaomi_path(fn):
    """XiaoMi资源: 优先 exe 同目录, 回退内置目录, 返回Path"""
    p = XIAOMI_DIR / fn
    if p.exists(): return p
    return BUNDLE_DIR / 'XiaoMi' / fn

def app_icon_path(fn):
    """应用图标: 优先 exe 同目录 assets/, 回退内置目录"""
    p = BASE_DIR / 'assets' / fn
    if p.exists(): return p
    return BUNDLE_DIR / 'assets' / fn

def get_short_path(path):
    """将中文长路径转换为Windows短路径(8.3格式)，解决cmd/adb中文乱码"""
    if not path: return path
    path = os.fspath(path)
    try:
        # 调用Windows API获取短路径
        GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
        GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
        GetShortPathNameW.restype = ctypes.c_uint
        buffer = ctypes.create_unicode_buffer(512)
        result = GetShortPathNameW(path, buffer, 512)
        if result > 0:
            return buffer.value
    except: pass
    return path

def _join_remote_target(d, name):
    """adb的目录目标探测在部分设备(如Android16)失效会报EISDIR,
    手动判断: 以'/'结尾或末段不含扩展名 → 视为目录, 拼上本地文件名"""
    if d.endswith('/'):
        return d + name
    tail = d.rsplit('/', 1)[-1]
    if tail and '.' not in tail:
        return d + '/' + name
    return d

BUNDLED_TOOLS = ('adb', 'fastboot', 'scrcpy')

def get_tool_path(tn):
    """adb/fastboot/scrcpy 工具路径: 严格使用打包内置(BUNDLE_DIR/tools),
    禁止回退到系统PATH的全局adb; 缺失时返回不存在的Path由调用方检查"""
    if tn in BUNDLED_TOOLS:
        return resource_path(tn + '.exe')
    return tn

# ── 内置图片加密 (打包后存为 .enc, 防止直接提取原图) ──
_IMG_KEY = b'XiaoMiFlashTool#2026#QR-Enc'
_IMG_ENC_SUFFIX = '.enc'

def _img_stream(key, salt, length):
    """SHA256计数器流密钥 (XOR对称加密/解密共用)"""
    out = bytearray(); counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(key + salt + counter.to_bytes(4, 'little')).digest())
        counter += 1
    return bytes(out[:length])

def img_xor(data, name):
    """加解密一体: 用文件名做salt, 保证每张图片密文不同"""
    key = _img_stream(_IMG_KEY, name.encode('utf-8'), len(data))
    return bytes(a ^ b for a, b in zip(data, key))

def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False


# ════════════════════════════════════════════
# 主窗口
# ════════════════════════════════════════════
class App(QMainWindow):
    # 跨线程信号 (工作线程→GUI线程)
    log_signal = Signal(str, str)        # (文本, 标签)
    status_signal = Signal(str)          # 状态栏文本
    finished_signal = Signal(str, str)   # (完成文本, 标签)
    done_signal = Signal(object)         # 回调对象

    def __init__(self):
        super().__init__()
        # ── Frameless: 自绘标题栏, 原生窗口行为由 startSystemMove/startSystemResize 代理 ──
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setWindowTitle("叶子Jinn的刷机工具 v1.0")
        ico = app_icon_path('app_icon.ico')
        if ico.exists():
            self.setWindowIcon(QIcon(str(ico)))
            if QApplication.instance():
                QApplication.instance().setWindowIcon(QIcon(str(ico)))
        self.resize(1120, 850)
        self.setMinimumSize(1000, 750)
        self.is_running = False
        self.current_process = None
        self._cmd_queue = []
        self._queue_lock = threading.Lock()
        self._build_ui()
        # 线程安全回灌 GUI
        self.log_signal.connect(self._log)
        self.status_signal.connect(self._set_status)
        self.finished_signal.connect(self._log)
        self.done_signal.connect(lambda fn: fn())
        QTimer.singleShot(300, self._check_tools)

    # ── 便捷工具 ──
    def _after(self, ms, fn):
        QTimer.singleShot(ms, fn)

    def _warn(self, title, msg):
        QMessageBox.warning(self, title, msg)
    def _error(self, title, msg):
        QMessageBox.critical(self, title, msg)
    def _info(self, title, msg):
        QMessageBox.information(self, title, msg)

    def _sep(self, parent):
        s = QFrame(parent)
        s.setFixedHeight(1)
        s.setProperty("fluentRole", "divider")
        return s

    # ── 按钮工厂 ──
    def _btn(self, parent, text, cmd, style='default', width=None, height=36, font=None, **kw):
        b = QPushButton(text, parent)
        b.setProperty("fluentAppearance", style)
        if width: b.setFixedWidth(int(width))
        if height: b.setMinimumHeight(int(height))
        if height and height <= 30:
            b.setProperty("fluentSize", "compact")
        if font:
            f = QFont(font[0], font[1] if len(font) > 1 else 10)
            if len(font) > 2 and font[2] == 'bold': f.setBold(True)
            b.setFont(f)
        if cmd: b.clicked.connect(lambda checked=False, c=cmd: c())
        b.setCursor(Qt.PointingHandCursor)
        return b

    def _label(self, parent, text, role=None, font=None):
        lbl = QLabel(text, parent)
        if role: lbl.setProperty("fluentRole", role)
        if font:
            f = QFont(font[0], font[1])
            if len(font) > 2 and font[2] == 'bold': f.setBold(True)
            lbl.setFont(f)
        return lbl

    def _radio(self, parent, text, group, value):
        rb = QRadioButton(text, parent)
        rb.setProperty('val', value)
        group.addButton(rb)
        return rb

    def _radio_value(self, group, default=None):
        b = group.checkedButton()
        return b.property('val') if b else default

    # ── 界面构建 ──
    def _build_ui(self):
        # 无边框窗口: 最外层 windowFrame (活动/非活动外框, 最大化时隐藏)
        frame = QWidget(self)
        frame.setObjectName("windowFrame")
        frame.setProperty("windowActive", True)
        frame.setProperty("windowMaximized", False)
        frame.setAttribute(Qt.WA_StyledBackground, True)
        self.setCentralWidget(frame)
        root = QVBoxLayout(frame)
        root.setContentsMargins(1, 1, 1, 1)  # 露出 windowFrame 外框
        root.setSpacing(0)
        self._frame_root = root

        # 自绘标题栏 (36px, 图标+标题+版本+窗口控制)
        ico = app_icon_path('app_icon.ico')
        self.title_bar = CustomTitleBar(
            icon_path=QIcon(str(ico)) if ico.exists() else None,
            title="叶子Jinn的刷机工具 v1.0",
            parent=frame)
        self.title_bar._attach_window(self)
        root.addWidget(self.title_bar)

        central = QWidget(frame)
        central.setObjectName("centralRoot")
        central.setAttribute(Qt.WA_StyledBackground, True)
        root.addWidget(central, 1)
        croot = QVBoxLayout(central)
        croot.setContentsMargins(0, 0, 0, 0)
        croot.setSpacing(0)

        # ── Notebook ──
        nb = QTabWidget(central)
        croot.addWidget(nb, 6)
        self._tab_device(nb); self._tab_magisk(nb); self._tab_recovery(nb)
        self._tab_files(nb); self._tab_advanced(nb); self._tab_screen(nb)

        # ── 底部: 左输出 + 右图片 ──
        bottom = QWidget(central)
        bl = QHBoxLayout(bottom); bl.setContentsMargins(12, 8, 12, 4); bl.setSpacing(8)
        self._build_output_panel(bl)
        self._build_qrcode(bl)
        croot.addWidget(bottom, 4)

        # ── 状态栏 ──
        sbar = QStatusBar(central)
        sbar.setSizeGripEnabled(False)
        self.status = self._label(sbar, "就绪")
        self.status.setProperty("fluentRole", "statusItem")
        sbar.addWidget(self.status)
        self.tool_status = self._label(sbar, "")
        sbar.addPermanentWidget(self.tool_status)
        croot.addWidget(sbar)

        # 缩放热区 (8个边缘/角) — 置于最上层
        self._resize_handles = WindowResizeHandles(frame)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        rh = getattr(self, '_resize_handles', None)
        if rh: rh.relayout()

    def _admin_badge(self, parent):
        """管理员指示器 (卡片式)"""
        af = QFrame(parent); af.setProperty("fluentRole", "panel")
        afl = QHBoxLayout(af); afl.setContentsMargins(10, 4, 10, 4); afl.setSpacing(6)
        ac = '管理员' if is_admin() else '非管理员'
        dot_role = 'ok' if is_admin() else 'err'
        afl.addWidget(self._label(af, "●", role=dot_role, font=('Microsoft YaHei UI', 8)))
        afl.addWidget(self._label(af, ac, role=dot_role, font=('Microsoft YaHei UI', 9, 'bold')))
        return af

    def _build_output_panel(self, bl):
        of = QFrame(); of.setProperty("fluentRole", "card")
        ol = QVBoxLayout(of); ol.setContentsMargins(12, 8, 12, 8); ol.setSpacing(6)
        oh = QHBoxLayout(); oh.setSpacing(6)
        oh.addWidget(self._label(of, "▸ 命令输出", role='consoleTitle'))
        oh.addStretch(1)
        oh.addWidget(self._admin_badge(of))
        oh.addWidget(self._btn(of, "终止命令", self._kill_cmd, 'danger', width=90, height=30))
        oh.addWidget(self._btn(of, "清空", self._clear_log, width=65, height=30))
        ol.addLayout(oh)
        self.output = QPlainTextEdit(of)
        self.output.setReadOnly(True)
        self.output.setFont(QFont('Consolas', 10))
        self.output.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        ol.addWidget(self.output, 1)
        bl.addWidget(of, 1)

    def _load_photo(self, fn):
        """加载图片: 外部原图(.png)优先, 否则解密内置 .enc, 全程内存操作"""
        p = xiaomi_path(fn)
        if p.exists():
            return QPixmap(str(p))
        enc = BUNDLE_DIR / 'XiaoMi' / (fn + _IMG_ENC_SUFFIX)
        if enc.exists():
            data = img_xor(enc.read_bytes(), fn)
            pm = QPixmap(); pm.loadFromData(data)
            return pm
        return QPixmap()

    def _build_qrcode(self, bl):
        right = QFrame(); right.setProperty("fluentRole", "card")
        right.setFixedWidth(360)
        right.setFixedHeight(260)
        gl = QGridLayout(right); gl.setContentsMargins(8, 8, 8, 8); gl.setSpacing(6)

        items = [
            ("_wxpay_thumb.png",  "微信收款", "微信收款.png"),
            ("_alipay_thumb.png", "支付宝收款", "支付宝收款.png"),
            ("_wxfriend_thumb.png","微信好友", "微信好友.png"),
            ("_qqfriend_thumb.png","QQ好友",   "QQ好友.png"),
        ]
        for idx, (thumb, label, orig) in enumerate(items):
            img = self._load_photo(thumb)
            if img.isNull(): continue
            cell = QFrame(right); cell.setProperty("fluentRole", "panel")
            cl = QVBoxLayout(cell); cl.setContentsMargins(4, 6, 4, 4); cl.setSpacing(2)
            iw = img.width(); ih = img.height()
            if iw > 94:
                r = 70.0 / iw; iw, ih = 70, int(ih * r)
            lbl = QLabel(cell)
            lbl.setPixmap(img.scaled(iw, ih, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            lbl.setAlignment(Qt.AlignCenter)
            cl.addWidget(lbl)
            bf = QHBoxLayout(); bf.setSpacing(4)
            bf.addWidget(self._label(cell, label, role='muted', font=('Microsoft YaHei UI', 9)))
            bf.addStretch(1)
            bf.addWidget(self._btn(cell, "原图", lambda o=orig: self._view_large(o), width=44, height=24, font=('Microsoft YaHei UI', 8)))
            cl.addLayout(bf)
            gl.addWidget(cell, idx // 2, idx % 2)
        for i in range(2):
            gl.setRowStretch(i, 1)
        for c in range(2):
            gl.setColumnStretch(c, 1)
        bl.addWidget(right, 0)

    def _view_large(self, fn):
        img = self._load_photo(fn)
        if img.isNull():
            self._warn("提示", "图片未找到"); return
        dlg = QDialog(self); dlg.setWindowTitle("查看原图 - " + os.path.basename(fn))
        dlg.setModal(True); dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        lay = QVBoxLayout(dlg); lay.setContentsMargins(16, 16, 16, 12)
        sc = QApplication.primaryScreen()
        sw, sh = sc.size().width(), sc.size().height() if sc else (1024, 768)
        w, h = img.width(), img.height()
        mw, mh = int(sw * 0.7), int(sh * 0.7)
        if w > mw or h > mh:
            r = min(mw / w, mh / h); w, h = int(w * r), int(h * r)
        pl = QLabel(dlg)
        pl.setPixmap(img.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        pl.setAlignment(Qt.AlignCenter)
        lay.addWidget(pl)
        lay.addWidget(self._btn(dlg, "关闭", dlg.accept, width=80, height=32), 0, Qt.AlignHCenter)
        dlg.resize(int(w * 1.02) + 32, int(h * 1.02) + 70)
        dlg.exec()

    # ── 工具方法 ──
    def _log(self, t, tag='info'):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(LOG_COLORS.get(tag, LOG_COLORS['info'])))
        cur = self.output.textCursor()
        cur.movePosition(QTextCursor.End)
        cur.setCharFormat(fmt)
        cur.insertText(t + '\n')
        self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum())

    def _set_status(self, t):
        self.status.setText(t)

    def _check_tools(self):
        a, f = os.path.exists(get_tool_path('adb')), os.path.exists(get_tool_path('fastboot'))
        self.tool_status.setText(f"ADB:[{'OK' if a else 'X'}]  Fastboot:[{'OK' if f else 'X'}]")
        if not (a and f): self._log("[!] adb.exe 或 fastboot.exe 未找到", 'warn')

    def _clear_log(self):
        self.output.clear()

    def _terminate(self, p, label="命令"):
        """通用进程终止"""
        if not p: return False
        try: p.terminate(); self._log(f"[!!] {label}已被用户终止", 'warn'); return True
        except Exception:
            try: p.kill(); self._log(f"[!!] {label}已被强制终止", 'warn'); return True
            except Exception: self._log(f"[!] 无法终止{label}进程", 'err'); return False

    def _kill_cmd(self):
        if self.current_process: self._terminate(self.current_process, "命令")
        else: self._log("[!] 当前没有正在执行的命令", 'warn')

    def _exec_subprocess(self, cmd, label, on_done=None, proc_attr='current_process'):
        """通用子进程执行 (Popen+readline+信号回灌), 消除重复
        proc_attr: 存储进程引用的属性名 ('current_process' 或 'scrpcy_process')
        """
        self._log(f">>> {' '.join(os.fspath(c) for c in cmd)}", 'cmd')
        self._set_status(f"执行中: {label}")
        self.is_running = True
        def w():
            try:
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                setattr(self, proc_attr, p)
                for raw in iter(p.stdout.readline, b''):
                    d = self._decode_out(raw).rstrip()
                    if d: self.log_signal.emit(d, 'info')
                p.wait(); r = p.returncode
                self.finished_signal.emit(f"[OK] 完成 (返回码: {r})" if r == 0 else f"[!!] 返回码: {r}",
                                          'ok' if r == 0 else 'warn')
            except Exception as e:
                self.finished_signal.emit(f"[ERR] {e}", 'err')
            finally:
                setattr(self, proc_attr, None); self.is_running = False
                self.status_signal.emit("就绪")
                if on_done: self.done_signal.emit(on_done)
        threading.Thread(target=w, daemon=True).start()

    def _decode_out(self, raw):
        """子进程输出解码: 优先UTF-8(adb/fastboot输出), 失败回退系统编码(GBK系统命令)"""
        try:
            return raw.decode('utf-8')
        except UnicodeDecodeError:
            return raw.decode(SYS_ENCODING, errors='replace')

    def _run(self, tool, args):
        """加入命令队列顺序执行"""
        with self._queue_lock:
            self._cmd_queue.append((tool, args))
            if not self.is_running:
                self._after(100, self._run_next)  # 等当前帧结束再启动

    def _run_next(self):
        with self._queue_lock:
            if not self._cmd_queue: return
            if self.is_running: return  # 已有命令在执行中
            tool, args = self._cmd_queue.pop(0)
            remaining = bool(self._cmd_queue)
        tp = get_tool_path(tool)
        if tool in BUNDLED_TOOLS and not tp.exists():
            self._log(f"[!] 未找到打包内置工具: {tool}.exe", 'err')
            if remaining: self._after(300, self._run_next)
            return
        cmd = [tp] + args
        self._exec_subprocess(cmd, f"{tool} {' '.join(args)}",
                              on_done=(lambda: self._after(300, self._run_next)) if remaining else None)

    def _run_file(self, fp, args=None):
        """执行本地exe/bat/ps1文件 (参数数组, 不经过CMD字符串拼接)"""
        fp = Path(fp)
        if not fp.exists():
            self._log(f"[!] 文件未找到: {fp}", 'warn')
            self._warn("提示", f"文件未找到:\n{fp}"); return
        ext = fp.suffix.lower()
        if ext == '.bat':
            # cmd.exe会二次解析路径, 中文/空格路径转8.3短路径规避乱码
            cmd = ['cmd', '/c', get_short_path(fp)]
        elif ext == '.ps1':
            cmd = ['powershell', '-ExecutionPolicy', 'Bypass', '-File', str(fp)]
        else:
            cmd = [str(fp)] + (args or [])
        self._exec_subprocess(cmd, fp.name)

    def _browse(self, title, mode='file', ext=None):
        """统一文件对话框 (mode: file/any/dir/save)"""
        start = str(BASE_DIR)
        if mode == 'dir':
            return QFileDialog.getExistingDirectory(self, title, start)
        if mode == 'save':
            e = ext or '.img'
            fn, _ = QFileDialog.getSaveFileName(self, title, os.path.join(start, ''),
                                                f"镜像文件 (*{e});;所有文件 (*.*)")
            return fn
        if mode == 'any':
            fn, _ = QFileDialog.getOpenFileName(self, title, start, "所有文件 (*.*)")
            return fn
        if ext:
            fn, _ = QFileDialog.getOpenFileName(self, title, start,
                                                f"{ext.upper()}文件 (*{ext});;所有文件 (*.*)")
            return fn
        fn, _ = QFileDialog.getOpenFileName(self, title, start, "镜像文件 (*.img);;所有文件 (*.*)")
        return fn

    def closeEvent(self, e):
        # 终止正在执行的命令和投屏进程
        for p in [self.current_process, getattr(self, 'scrpcy_process', None)]:
            if p:
                try: p.terminate()
                except: pass
        # 强制结束ADB/Fastboot/Scrcpy进程(释放临时目录文件句柄, 避免PyInstaller清理失败弹窗)
        for exe in ['adb.exe', 'fastboot.exe', 'scrcpy.exe']:
            try: subprocess.run(['taskkill', '/f', '/im', exe], capture_output=True,
                                creationflags=subprocess.CREATE_NO_WINDOW)
            except: pass
        e.accept()

    # ════════════════════════════════════════════
    # Tab 1: 设备信息
    # ════════════════════════════════════════════
    def _tab_device(self, nb):
        page = QScrollArea(nb); page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)
        nb.addTab(page, "  设备信息  ")
        tab = QWidget(page); page.setWidget(tab)
        v = QVBoxLayout(tab); v.setContentsMargins(18, 12, 18, 12); v.setSpacing(8)

        f1 = QGroupBox("ADB 设备信息 (手机需开启USB调试)", tab)
        r1 = QHBoxLayout(f1); r1.setContentsMargins(12, 8, 12, 8); r1.setSpacing(6)
        for t, x, a in [("检测ADB设备", "adb", ["devices"]), ("查看机型", "adb", ["shell", "getprop", "ro.product.name"]), ("查看内核", "adb", ["shell", "uname", "-r"])]:
            r1.addWidget(self._btn(f1, t, lambda x=x, a=a: self._run(x, a), width=140))
        r1.addStretch(1)
        v.addWidget(f1)

        f2 = QGroupBox("Fastboot 设备信息 (手机需在Fastboot模式)", tab)
        r2 = QVBoxLayout(f2); r2.setContentsMargins(12, 8, 12, 8); r2.setSpacing(4)
        row1 = QHBoxLayout(); row1.setSpacing(6)
        for t, x, a in [("检测设备", "fastboot", ["devices"]), ("查看机型", "fastboot", ["getvar", "product"]), ("查看Slot", "fastboot", ["getvar", "current-slot"])]:
            row1.addWidget(self._btn(f2, t, lambda x=x, a=a: self._run(x, a), width=120))
        row1.addStretch(1)
        row2 = QHBoxLayout(); row2.setSpacing(6)
        for t, x, a in [("BL锁(骁龙)", "fastboot", ["oem", "device-info"]), ("BL锁(天玑)", "fastboot", ["oem", "lks"])]:
            row2.addWidget(self._btn(f2, t, lambda x=x, a=a: self._run(x, a), width=125))
        row2.addStretch(1)
        r2.addLayout(row1); r2.addLayout(row2)
        v.addWidget(f2)

        f3 = QGroupBox("重启操作", tab)
        r3 = QHBoxLayout(f3); r3.setContentsMargins(12, 8, 12, 8); r3.setSpacing(6)
        for t, x, a in [("重启到Fastboot", "adb", ["reboot", "bootloader"]), ("重启到Recovery", "fastboot", ["reboot", "recovery"])]:
            r3.addWidget(self._btn(f3, t, lambda x=x, a=a: self._run(x, a), width=150))
        r3.addWidget(self._btn(f3, "重启系统", self._reboot_both, width=150))
        r3.addStretch(1)
        v.addWidget(f3)
        v.addStretch(1)

    def _reboot_both(self):
        """先adb reboot, 再接fastboot reboot"""
        self._run("adb", ["reboot"])
        self._run("fastboot", ["reboot"])

    # ════════════════════════════════════════════
    # Tab 2: 刷入面具
    # ════════════════════════════════════════════
    def _tab_magisk(self, nb):
        page = QScrollArea(nb); page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)
        nb.addTab(page, "  刷入面具  ")
        tab = QWidget(page); page.setWidget(tab)
        v = QVBoxLayout(tab); v.setContentsMargins(18, 12, 18, 12); v.setSpacing(8)

        v.addWidget(self._label(tab, "将Magisk/KernelSU镜像刷入boot分区以获取ROOT权限", role='muted'))

        sf = QHBoxLayout(); sf.setSpacing(6)
        sf.addWidget(self._label(tab, "镜像文件:"))
        self.magisk_var = QLineEdit(str(BASE_DIR / "2.img"), tab)
        sf.addWidget(self.magisk_var, 1)
        sf.addWidget(self._btn(tab, "浏览...", self._sel_magisk, width=78, height=32))
        v.addLayout(sf)

        ff = QGroupBox("刷入方式", tab)
        fl = QVBoxLayout(ff); fl.setContentsMargins(18, 8, 12, 8); fl.setSpacing(2)
        self.flash_group = QButtonGroup(self)
        for t, val in [("flash boot (865-)", "boot"), ("flash init_boot (870+)", "init_boot"), ("flash init_boot_ab (K60Ultra)", "init_boot_ab")]:
            rb = self._radio(ff, t, self.flash_group, val)
            if val == "boot": rb.setChecked(True)
            fl.addWidget(rb)
        v.addWidget(ff)

        bf = QHBoxLayout(); bf.setSpacing(6)
        bf.addWidget(self._btn(tab, "开始刷入", self._do_flash_magisk, 'primary', width=115))
        bf.addWidget(self._btn(tab, "重启系统", lambda: self._run("fastboot", ["reboot"]), width=100))
        bf.addStretch(1)
        v.addLayout(bf)

        v.addWidget(self._sep(tab))
        v.addWidget(self._label(tab, "从手机拉取boot镜像", role='section'))

        pf1 = QHBoxLayout(); pf1.setSpacing(6)
        pf1.addWidget(self._label(tab, "手机路径:"))
        self.pull_boot_src = QLineEdit("/storage/emulated/0/Download/2.img", tab)
        pf1.addWidget(self.pull_boot_src, 1)
        v.addLayout(pf1)
        pf2 = QHBoxLayout(); pf2.setSpacing(6)
        pf2.addWidget(self._label(tab, "保存到:"))
        self.pull_boot_dst = QLineEdit(str(BASE_DIR / "2.img"), tab)
        pf2.addWidget(self.pull_boot_dst, 1)
        pf2.addWidget(self._btn(tab, "浏览...", self._sel_pull_boot_dst, width=78, height=32))
        pf2.addWidget(self._btn(tab, "拉取", self._do_pull_boot, 'primary', width=105))
        v.addLayout(pf2)
        v.addStretch(1)

    def _sel_magisk(self):
        p = self._browse("选择img镜像")
        if p: self.magisk_var.setText(p)
    def _sel_pull_boot_dst(self):
        p = self._browse("保存boot镜像", mode='save')
        if p: self.pull_boot_dst.setText(p)
    def _do_flash_magisk(self):
        img = self.magisk_var.text().strip()
        if not img or not os.path.exists(img): self._warn("提示", "请先选择有效的镜像文件"); return
        self._run("fastboot", ["flash", self._radio_value(self.flash_group, "boot"), img])
    def _do_pull_boot(self):
        s = self.pull_boot_src.text().strip(); d = self.pull_boot_dst.text().strip()
        if not d: self._warn("提示", "请填写保存路径"); return
        self._run("adb", ["pull", s, d])

    # ════════════════════════════════════════════
    # Tab 3: 刷Recovery
    # ════════════════════════════════════════════
    def _tab_recovery(self, nb):
        page = QScrollArea(nb); page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)
        nb.addTab(page, "  刷Recovery  ")
        tab = QWidget(page); page.setWidget(tab)
        v = QVBoxLayout(tab); v.setContentsMargins(18, 12, 18, 12); v.setSpacing(8)

        v.addWidget(self._label(tab, "刷入Recovery镜像 (TWRP等)", role='muted'))

        sf = QHBoxLayout(); sf.setSpacing(6)
        sf.addWidget(self._label(tab, "Recovery镜像:"))
        self.recov_var = QLineEdit(tab)
        sf.addWidget(self.recov_var, 1)
        sf.addWidget(self._btn(tab, "浏览...", self._sel_recov, width=78, height=32))
        v.addLayout(sf)

        ff = QGroupBox("刷入方式", tab)
        fl = QVBoxLayout(ff); fl.setContentsMargins(18, 8, 12, 8); fl.setSpacing(2)
        self.recov_group = QButtonGroup(self)
        for t, val in [("仅刷recovery (骁龙865-)", "recovery_only"), ("刷recovery_a + recovery_b (骁龙8G+)", "recovery_ab"), ("刷misc.bin + recovery (骁龙855-)", "misc_recovery"), ("临时启动 (不写入)", "boot_temp")]:
            rb = self._radio(ff, t, self.recov_group, val)
            if val == "recovery_only": rb.setChecked(True)
            fl.addWidget(rb)
        v.addWidget(ff)

        bf = QHBoxLayout(); bf.setSpacing(6)
        bf.addWidget(self._btn(tab, "开始刷入", self._do_flash_recov, 'primary', width=150))
        bf.addWidget(self._btn(tab, "重启进入Recovery", lambda: self._run("fastboot", ["reboot", "recovery"]), width=150))
        bf.addStretch(1)
        v.addLayout(bf)
        v.addStretch(1)

    def _sel_recov(self):
        p = self._browse("选择Recovery镜像")
        if p: self.recov_var.setText(p)
    def _do_flash_recov(self):
        img = self.recov_var.text().strip()
        if not img or not os.path.exists(img): self._warn("提示", "请先选择Recovery镜像"); return
        m = self._radio_value(self.recov_group, "recovery_only")
        if m == "recovery_only": self._run("fastboot", ["flash", "recovery", img])
        elif m == "recovery_ab":
            self._run("fastboot", ["flash", "recovery_a", img]); self._run("fastboot", ["flash", "recovery_b", img])
        elif m == "misc_recovery":
            misc = resource_path("misc.bin")
            if misc.exists(): self._run("fastboot", ["flash", "misc", misc])
            else: self._log("[!] misc.bin未找到, 跳过misc刷入", 'warn')
            self._run("fastboot", ["flash", "recovery", img])
        elif m == "boot_temp": self._run("fastboot", ["boot", img])

    # ════════════════════════════════════════════
    # Tab 4: 文件管理
    # ════════════════════════════════════════════
    def _tab_files(self, nb):
        page = QScrollArea(nb); page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)
        nb.addTab(page, "  文件管理  ")
        tab = QWidget(page); page.setWidget(tab)
        v = QVBoxLayout(tab); v.setContentsMargins(18, 12, 18, 12); v.setSpacing(8)

        f1 = QGroupBox("安装APK", tab)
        r1 = QHBoxLayout(f1); r1.setContentsMargins(12, 8, 12, 8); r1.setSpacing(6)
        r1.addWidget(self._label(f1, "APK:"))
        self.apk_var = QLineEdit(f1)
        r1.addWidget(self.apk_var, 1)
        r1.addWidget(self._btn(f1, "浏览...", self._sel_apk, width=78, height=32))
        r1.addWidget(self._btn(f1, "安装", self._do_install_apk, 'green', width=105))
        v.addWidget(f1)

        f2 = QGroupBox("推送到手机 (adb push)", tab)
        c2 = QVBoxLayout(f2); c2.setContentsMargins(12, 8, 12, 8); c2.setSpacing(4)
        r2a = QHBoxLayout(); r2a.setSpacing(6)
        r2a.addWidget(self._label(f2, "取电脑文件:"))
        self.push_src = QLineEdit(f2)
        r2a.addWidget(self.push_src, 1)
        r2a.addWidget(self._btn(f2, "文件", self._sel_push_src, width=85, height=30))
        r2a.addWidget(self._btn(f2, "文件夹", self._sel_push_dir, width=85, height=30))
        c2.addLayout(r2a)
        r2b = QHBoxLayout(); r2b.setSpacing(6)
        r2b.addWidget(self._label(f2, "存手机路径:"))
        self.push_dst = QLineEdit("/storage/emulated/0/", f2)
        r2b.addWidget(self.push_dst, 1)
        r2b.addWidget(self._btn(f2, "推送", self._do_push, 'primary', width=105))
        c2.addLayout(r2b)
        v.addWidget(f2)

        f3 = QGroupBox("从手机拉取文件 (adb pull)", tab)
        c3 = QVBoxLayout(f3); c3.setContentsMargins(12, 8, 12, 8); c3.setSpacing(4)
        r3a = QHBoxLayout(); r3a.setSpacing(6)
        r3a.addWidget(self._label(f3, "取手机文件:"))
        self.pull_src = QLineEdit("/storage/emulated/0/Download/2.img", f3)
        r3a.addWidget(self.pull_src, 1)
        c3.addLayout(r3a)
        r3b = QHBoxLayout(); r3b.setSpacing(6)
        r3b.addWidget(self._label(f3, "存电脑路径:"))
        self.pull_dst = QLineEdit(str(BASE_DIR), f3)
        r3b.addWidget(self.pull_dst, 1)
        r3b.addWidget(self._btn(f3, "浏览...", self._sel_pull_dst, width=78, height=32))
        r3b.addWidget(self._btn(f3, "拉取", self._do_pull, 'primary', width=105))
        c3.addLayout(r3b)
        v.addWidget(f3)
        v.addStretch(1)

    def _sel_apk(self):
        p = self._browse("选择APK", ext='.apk')
        if p: self.apk_var.setText(p)
    def _sel_push_src(self):
        p = self._browse("选择文件", mode='any')
        if p: self.push_src.setText(p)
    def _sel_push_dir(self):
        p = self._browse("选择文件夹", mode='dir')
        if p: self.push_src.setText(p)
    def _sel_pull_dst(self):
        p = self._browse("选择保存目录", mode='dir')
        if p: self.pull_dst.setText(p)
    def _do_install_apk(self):
        a = self.apk_var.text().strip()
        if not a or not os.path.exists(a): self._warn("提示", "请选择APK文件"); return
        # 直接传Unicode路径: adb经CreateProcessW(参数数组)原生支持中文, 短路径反而会变中文+~1乱码
        self._run("adb", ["install", a])
    def _do_push(self):
        s, d = self.push_src.text().strip(), self.push_dst.text().strip()
        if not s or not os.path.exists(s): self._warn("提示", "请选择源文件"); return
        if not d: self._warn("提示", "请填写手机路径"); return
        # 目录目标显式拼上文件名 (Android16等设备adbd目录探测失效→EISDIR)
        d = _join_remote_target(d, os.path.basename(s.rstrip('/\\')))
        self._run("adb", ["push", s, d])
    def _do_pull(self):
        s, d = self.pull_src.text().strip(), self.pull_dst.text().strip()
        if not s or not d: self._warn("提示", "请填写路径"); return
        # pull到本地目录时adb会自行算文件名并截断中文, 显式拼上远程文件名
        if os.path.isdir(d):
            d = os.path.join(d, os.path.basename(s.rstrip('/')))
        self._run("adb", ["pull", s, d])

    # ════════════════════════════════════════════
    # Tab 5: 高级功能
    # ════════════════════════════════════════════
    def _tab_advanced(self, nb):
        page = QScrollArea(nb); page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)
        nb.addTab(page, "  高级功能  ")
        tab = QWidget(page); page.setWidget(tab)
        v = QVBoxLayout(tab); v.setContentsMargins(18, 12, 18, 12); v.setSpacing(10)

        # ── 分组1: 系统维护 (5 个按钮同一行) ──
        g1 = QGroupBox("系统维护", tab)
        r1 = QHBoxLayout(g1); r1.setContentsMargins(12, 10, 12, 12); r1.setSpacing(6)
        sys_btns = [
            ("执行BL解锁", lambda: self._run("fastboot", ["flashing", "unlock"]), 'danger'),
            ("修复hosts加速下载", self._fix_hosts, 'default'),
            ("修复USB驱动注册表", self._fix_usb, 'default'),
            ("刷新DNS缓存", lambda: self._run("ipconfig", ["/flushdns"]), 'default'),
            ("打开命令参考", self._open_quick_cmd, 'outline'),
        ]
        for txt, cmd, st in sys_btns:
            b = self._btn(g1, txt, cmd, st, height=36)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            r1.addWidget(b, 1)
        v.addWidget(g1)

        # ── 分组2: 刷入 vbmeta ──
        g2 = QGroupBox("刷入 vbmeta", tab)
        r2 = QHBoxLayout(g2); r2.setContentsMargins(12, 10, 12, 12); r2.setSpacing(8)
        r2.addWidget(self._label(g2, "镜像文件:"))
        self.vbmeta_var = QLineEdit(g2)
        r2.addWidget(self.vbmeta_var, 1)
        r2.addWidget(self._btn(g2, "浏览...", self._sel_vbmeta, width=78, height=32))
        r2.addWidget(self._btn(g2, "刷入(禁用验证)", self._do_vbmeta, 'primary', width=150))
        v.addWidget(g2)

        # ── 分组3: 自定义命令 ──
        g3 = QGroupBox("自定义命令", tab)
        c3 = QVBoxLayout(g3); c3.setContentsMargins(12, 10, 12, 12); c3.setSpacing(8)
        r3 = QHBoxLayout(); r3.setSpacing(8)
        r3.addWidget(self._label(g3, "命令:"))
        self.cmd_var = QLineEdit(g3)
        r3.addWidget(self.cmd_var, 1)
        r3.addWidget(self._btn(g3, "执行", self._do_custom, 'primary'))
        c3.addLayout(r3)
        r4 = QHBoxLayout(); r4.setSpacing(8)
        r4.addWidget(self._label(g3, "提示: 输入 adb/fastboot 命令并回车, 支持系统命令如 ipconfig", role='muted'))
        r4.addStretch(1)
        c3.addLayout(r4)
        v.addWidget(g3)

        # ── 分组4: 实用工具 (6 个按钮同一行) ──
        g4 = QGroupBox("实用工具", tab)
        r6 = QHBoxLayout(g4); r6.setContentsMargins(12, 10, 12, 12); r6.setSpacing(6)
        tool_btns = [
            ("设备管理器", self._open_devmgmt, 'default'),
            ("内存清理 (Cleaner)", lambda: self._run_file(xiaomi_path("WinMemoryCleaner.exe")), 'green'),
            ("安装安卓驱动 (OPPO)", lambda: self._run_file(xiaomi_path("OPPO.exe")), 'primary'),
            ("安装压缩工具 (Bandizip)", lambda: self._run_file(xiaomi_path("Bandizipv6.29.exe")), 'primary'),
            ("关闭文件警告 (bat)", lambda: self._run_file(xiaomi_path("DisableAllFileWarnings.bat")), 'default'),
            ("关闭文件警告 (ps1)", lambda: self._run_file(xiaomi_path("DisableAllFileWarnings.ps1")), 'default'),
        ]
        for txt, cmd, st in tool_btns:
            b = self._btn(g4, txt, cmd, st, height=36)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            r6.addWidget(b, 1)
        v.addWidget(g4)
        v.addStretch(1)

    def _open_devmgmt(self):
        self._log(">>> 打开设备管理器", 'cmd')
        try: os.startfile('devmgmt.msc'); self._log("[OK] 设备管理器已打开", 'ok')
        except Exception as e: self._log(f"[ERR] {e}", 'err')

    def _sel_vbmeta(self):
        p = self._browse("选择vbmeta镜像")
        if p: self.vbmeta_var.setText(p)
    def _do_vbmeta(self):
        img = self.vbmeta_var.text().strip()
        if not img or not os.path.exists(img): self._warn("提示", "请选择vbmeta镜像"); return
        self._run("fastboot", ["--disable-verity", "--disable-verification", "flash", "vbmeta", img])
    def _do_custom(self):
        s = self.cmd_var.text().strip()
        if not s: return
        try:
            p = shlex.split(s)
            if not p: return
            self._run(p[0], p[1:])
        except Exception as e:
            self._log(f"[ERR] 命令解析失败: {e}", 'err')

    def _open_quick_cmd(self):
        c = """B站：叶子Jinn

fastboot oem device-info
fastboot oem lks

fastboot flash misc misc.bin
fastboot flash recovery twrp.img
fastboot flash recovery recovery.img
fastboot flash recovery_a      
fastboot flash recovery_b
fastboot boot twrp.img
fastboot reboot recovery
fastboot flash boot boot.img
fastboot flash init_boot init_boot.img

adb devices
adb shell uname -r
adb shell getprop ro.product.name

adb reboot bootloader

fastboot devices
fastboot getvar product

fastboot flash boot 2.img
fastboot reboot
fastboot.exe --disable-verity --disable-verification flash vbmeta vbmeta.img
fastboot flash vbmeta vbmeta.img
ipconfig /flushdns
adb nodaemon server
fastboot getvar current-slot    fastboot --set-active=a         fastboot --set-active=b
adb pull "/storage/emulated/0/MIUI/backup/AllBackup" "D:\\XiaoMi\\AllBackup"
fastboot flashing unlock
fastboot oem set-gpu-preemption 0 androidboot.selinux=permissive
fastboot continue
fastboot oem set-gpu-preemption 1"""
        dlg = QDialog(self); dlg.setWindowTitle("快捷命令参考")
        dlg.setModal(True); dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        lay = QVBoxLayout(dlg); lay.setContentsMargins(16, 12, 16, 12)
        lay.addWidget(self._label(dlg, "常用命令参考", role='section', font=('Microsoft YaHei UI', 12, 'bold')))
        txt = QPlainTextEdit(dlg)
        txt.setReadOnly(True); txt.setFont(QFont('Consolas', 10))
        txt.insertPlainText(c)
        lay.addWidget(txt, 1)
        lay.addWidget(self._btn(dlg, "关闭", dlg.accept, width=80, height=32), 0, Qt.AlignHCenter)
        dlg.resize(640, 520)
        dlg.exec()

    def _fix_hosts(self):
        if not is_admin(): self._error("错误", "需要管理员权限!"); return
        try:
            hp = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'System32' / 'drivers' / 'etc' / 'hosts'
            with open(hp, 'r', encoding='utf-8', errors='ignore') as f: c = f.read()
            if 'bigota.d.miui.com' in c: self._log("[OK] hosts已包含小米节点", 'ok'); return
            with open(hp, 'a', encoding='utf-8') as f: f.write("\n#小米刷机包下载加速\n47.74.196.250 bigota.d.miui.com\n47.74.196.250 hugeota.d.miui.com\n")
            self._log("[OK] hosts已更新", 'ok'); self._run("ipconfig", ["/flushdns"])
        except Exception as e: self._log(f"[ERR] {e}", 'err')

    def _fix_usb(self):
        if not is_admin(): self._error("错误", "需要管理员权限!"); return
        self._log("[*] 开始修复USB驱动注册表...", 'info')
        for n, v in [("osvc", "0000"), ("SkipContainerIdQuery", "01000000"), ("SkipBOSDescriptorQuery", "01000000")]:
            try:
                r = subprocess.run(['reg', 'add', r'HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\usbflags\18D1D00D0100', '/v', n, '/t', 'REG_BINARY', '/d', v, '/f'],
                    capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                if r.returncode == 0: self._log(f"[OK] 注册表已写入: {n}", 'ok')
                else: self._log(f"[!!] 注册表写入失败: {n} - {r.stderr.strip()}", 'warn')
            except Exception as e: self._log(f"[ERR] 注册表写入异常: {e}", 'err')
        self._log("[OK] USB驱动注册表修复完成", 'ok')

    # ════════════════════════════════════════════
    # Tab 7: 投屏控制
    # ════════════════════════════════════════════
    def _tab_screen(self, nb):
        page = QScrollArea(nb); page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)
        nb.addTab(page, "  投屏控制  ")
        tab = QWidget(page); page.setWidget(tab)
        v = QVBoxLayout(tab); v.setContentsMargins(18, 12, 18, 12); v.setSpacing(8)
        self.scrpcy_process = None
        self._device_serial = None  # 当前设备序列号

        r1 = QHBoxLayout(); r1.setSpacing(6)
        r1.addWidget(self._btn(tab, "开始投屏", self._start_scrcpy, 'green', width=140, height=40))
        r1.addWidget(self._btn(tab, "结束投屏", self._stop_scrcpy, 'danger', width=140, height=40))
        r1.addWidget(self._btn(tab, "结束ADB进程", lambda: self._run("adb", ["kill-server"]), width=140, height=40))
        r1.addStretch(1)
        v.addLayout(r1)

        # 自动息屏勾选框
        self.auto_screen_off = QCheckBox("自动息屏 (投屏时关闭手机屏幕)", tab)
        v.addWidget(self.auto_screen_off)

        v.addWidget(self._label(tab, "投屏参数:", role='section'))
        r2 = QHBoxLayout(); r2.setSpacing(6)
        r2.addWidget(self._label(tab, "码率:"))
        self.scrpy_bitrate = QLineEdit("8000000", tab); self.scrpy_bitrate.setFixedWidth(90)
        r2.addWidget(self.scrpy_bitrate)
        r2.addWidget(self._label(tab, "(默认8M, 越高越清晰)", role='muted'))
        r2.addWidget(self._label(tab, "  分辨率上限:"))
        self.scrpy_maxsize = QLineEdit("0", tab); self.scrpy_maxsize.setFixedWidth(70)
        r2.addWidget(self.scrpy_maxsize)
        r2.addWidget(self._label(tab, "(0=原尺寸)", role='muted'))
        r2.addStretch(1)
        v.addLayout(r2)

        v.addWidget(self._sep(tab))
        v.addWidget(self._label(tab, "手机导航键 (鼠标点击):", role='section'))
        r3 = QHBoxLayout(); r3.setSpacing(6)
        for l, c in [("← 返回", 4), ("■ 主页", 3), ("□ 后台", 187)]:
            r3.addWidget(self._btn(tab, l, lambda c=c: self._adb_key(c), 'primary', width=110, height=36))
        r3.addStretch(1)
        v.addLayout(r3)

        v.addWidget(self._sep(tab))
        v.addWidget(self._label(tab, "其他快捷操作:", role='section'))
        r4 = QHBoxLayout(); r4.setSpacing(6)
        for l, c in [("电源", 26), ("音量+", 24), ("音量-", 25), ("截图", 276), ("展开通知栏", 83)]:
            r4.addWidget(self._btn(tab, l, lambda c=c: self._adb_key(c), width=105, height=34))
        r4.addStretch(1)
        v.addLayout(r4)
        v.addStretch(1)

    def _get_device_serial(self):
        """获取当前连接的设备序列号"""
        adb = get_tool_path('adb')
        if not adb.exists():
            self._log("[!] 未找到打包内置 adb.exe", 'err')
            return None
        try:
            r = subprocess.run([adb, 'devices', '-l'], capture_output=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            out = self._decode_out(r.stdout) if r.stdout else ''
            lines = out.strip().split('\n')
            devices = []
            for line in lines[1:]:  # 跳过标题行
                if line.strip() and 'device' in line:
                    parts = line.split()
                    if parts:
                        devices.append(parts[0])  # 序列号
            if len(devices) == 0:
                return None
            if len(devices) == 1:
                return devices[0]
            # 多设备: 返回第一个(或让用户选择)
            self._log(f"[!] 检测到 {len(devices)} 个设备: {', '.join(devices)}", 'warn')
            return devices[0]  # 默认用第一个
        except Exception as e:
            self._log(f"[ERR] 获取设备序列号失败: {e}", 'err')
            return None

    def _start_scrcpy(self):
        sp = get_tool_path('scrcpy')
        if not os.path.exists(sp): self._warn("提示", "scrcpy.exe 未找到"); return

        # 获取设备序列号 (用独立subprocess.run, 不经过队列)
        self._device_serial = self._get_device_serial()
        if not self._device_serial:
            self._warn("提示", "未检测到ADB设备，请确保手机已连接并开启USB调试")
            return

        self._log(f"[OK] 设备序列号: {self._device_serial}", 'ok')

        br = self.scrpy_bitrate.text().strip() or "8000000"
        ms = self.scrpy_maxsize.text().strip() or "0"
        a = ["-s", self._device_serial, "--stay-awake", "--no-audio", "--video-bit-rate", br]
        if self.auto_screen_off.isChecked():
            a.append("--turn-screen-off")
        if ms != "0": a.extend(["--max-size", ms])

        # 投屏完全独立: 不经过队列, 不占用is_running, 输出不显示
        self._log("[OK] 启动投屏中...", 'ok')
        try:
            p = subprocess.Popen([sp] + a, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
            self.scrpcy_process = p
            self._log("[OK] 投屏已启动 (独立运行, 不影响其他功能)", 'ok')
        except Exception as e:
            self._log(f"[ERR] 投屏启动失败: {e}", 'err')

    def _stop_scrcpy(self):
        if self.scrpcy_process:
            try:
                self.scrpcy_process.terminate()
                self.scrpcy_process.wait(timeout=3)
            except:
                try: self.scrpcy_process.kill()
                except: pass
            self.scrpcy_process = None
            self._log("[OK] 投屏已关闭", 'ok')
        else: self._log("[!] 当前没有投屏进程", 'warn')

    def _adb_key(self, c):
        """发送按键事件 - 独立执行, 不经过队列"""
        if not self._device_serial:
            self._log("[!] 未获取设备序列号，请先开始投屏", 'warn')
            return
        adb = get_tool_path('adb')
        try:
            subprocess.Popen([adb, "-s", self._device_serial, "shell", "input", "keyevent", str(c)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW)
            self._log(f"[OK] 按键: {c}", 'ok')
        except Exception as e:
            self._log(f"[ERR] 按键失败: {e}", 'err')

    def _apply_dark_titlebar(self):
        """Windows: 若系统仍绘制原生标题栏 (非Frameless时), 强制DWM深色;
        Frameless 模式下本方法无副作用, 供回退使用"""
        if sys.platform != 'win32':
            return
        try:
            hwnd = int(self.winId())
            value = ctypes.c_int(1)
            dwm = ctypes.windll.dwmapi
            for attr in (20, 19):
                r = dwm.DwmSetWindowAttribute(
                    ctypes.c_void_p(hwnd), ctypes.c_int(attr),
                    ctypes.byref(value), ctypes.sizeof(value))
                if r == 0:
                    break
        except Exception:
            pass

    def changeEvent(self, e):
        """同步 最大化/还原 与 激活/失焦 状态到标题栏与窗口外框"""
        super().changeEvent(e)
        if e.type() == QEvent.WindowStateChange:
            tb = getattr(self, 'title_bar', None)
            if tb: tb.sync_max_state()
            self._sync_frame_state()
        elif e.type() == QEvent.ActivationChange:
            tb = getattr(self, 'title_bar', None)
            if tb: tb.sync_active()
            self._sync_frame_state()

    def _sync_frame_state(self):
        """windowFrame: 激活外框颜色 + 最大化时隐藏外框"""
        frame = self.centralWidget()
        if not frame or frame.objectName() != "windowFrame":
            return
        active = self.isActiveWindow()
        maximized = self.isMaximized()
        if frame.property("windowActive") != active:
            frame.setProperty("windowActive", active)
        if frame.property("windowMaximized") != maximized:
            frame.setProperty("windowMaximized", maximized)
        # 最大化时去除 1px 外框边距, 让内容铺满工作区
        root = getattr(self, '_frame_root', None)
        if root:
            m = 0 if maximized else 1
            root.setContentsMargins(m, m, m, m)
        frame.style().unpolish(frame)
        frame.style().polish(frame)
        frame.update()
        # 缩放热区在最大化时无意义
        rh = getattr(self, '_resize_handles', None)
        if rh: rh.setVisible(not maximized)

    def showEvent(self, e):
        super().showEvent(e)
        self._sync_frame_state()
        tb = getattr(self, 'title_bar', None)
        if tb:
            tb.sync_active()
            tb.sync_max_state()

    def run(self):
        try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except: pass
        self.show()
        self._sync_frame_state()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    apply_theme(app)
    win = App()
    win.run()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
