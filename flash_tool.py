# -*- coding: utf-8 -*-
"""
小米刷机助手 - XiaoMi Flash Tool v2.1
单文件exe, Win7-11 64位, 零外部依赖
"""

import os, sys, subprocess, threading, ctypes, locale, shlex, hashlib, base64
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

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
            import tkinter.messagebox as mb
            mb.showerror("完整性校验失败", "程序已被篡改或损坏！\n请从官方渠道重新下载。")
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

# ── 高级暗色主题 (深靛蓝通透质感) ──
C = {
    'bg':'#080810','surface':'#111128','card':'#18183a','overlay':'#222250',
    'text':'#e2e8f0','subtext':'#7f8cbd','blue':'#6366f1','blue_light':'#818cf8',
    'blue_dim':'#4f46e5','green':'#10b981','green_light':'#34d399','red':'#ef4444',
    'red_light':'#f87171','yellow':'#f59e0b','yellow_light':'#fbbf24','purple':'#8b5cf6',
    'cyan':'#06b6d4','dark':'#060612','border':'#252550','shadow':'#020206',
    'accent':'#6366f1','accent_dim':'#4338ca',
}

# ════════════════════════════════════════════
# Canvas圆角按钮 (阴影+悬停+按压)
# ════════════════════════════════════════════
class RoundedButton(tk.Canvas):
    def __init__(self, master, text="", command=None, width=None, height=36,
                 radius=10, bg_color=None, fg_color=None, hover_bg=None, hover_fg=None,
                 active_bg=None, active_fg=None, font=None, shadow=True, accent=None, **kw):
        if bg_color is None: bg_color = C['card']
        if fg_color is None: fg_color = C['text']
        if hover_bg is None: hover_bg = C['overlay']
        if hover_fg is None: hover_fg = C['text']
        if active_bg is None: active_bg = C['blue']
        if active_fg is None: active_fg = '#ffffff'
        if accent is None:
            accent = C.get('accent', C['blue'])
        if width is None:
            cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
            width = cjk*17 + (len(text)-cjk)*9 + 44
        sp = 4 if shadow else 0
        super().__init__(master, width=width+sp, height=height+sp, bg=C['bg'], highlightthickness=0, **kw)
        self._t=text; self._cmd=command; self._bg=bg_color; self._fg=fg_color
        self._hbg=hover_bg; self._hfg=hover_fg; self._abg=active_bg; self._afg=active_fg
        self._accent=accent
        self._font=font or ('Microsoft YaHei UI',10); self._r=radius; self._shadow=shadow; self._en=True
        self.bind('<Configure>', lambda e: self.after(5, lambda: self._draw(self._bg,self._fg)))
        self.bind('<Enter>', lambda e: self._draw(self._hbg,self._hfg))
        self.bind('<Leave>', lambda e: self._draw(self._bg,self._fg))
        self.bind('<Button-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)

    def _rrect(self, x1, y1, x2, y2, r, **kw):
        pts=[x1+r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y2-r, x2,y2, x2-r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _draw(self, bg, fg):
        self.delete('all')
        w=self.winfo_width(); h=self.winfo_height()
        if w<4 or h<4: return
        if self._shadow: self._rrect(3,3,w-1,h-1,self._r, fill=C['shadow'], outline='')
        self._rrect(1,1,w-4,h-4,self._r, fill=bg, outline='')
        # 底部强调色细条 (2px高, 80%宽, 居中)
        bar_w = int((w-8)*0.7); bar_x = (w-bar_w)//2; bar_y = h-6
        self.create_rectangle(bar_x, bar_y, bar_x+bar_w, bar_y+2, fill=self._accent, outline='')
        self.create_text((w-3)//2,(h-3)//2, text=self._t, fill=fg, font=self._font, anchor=tk.CENTER)

    def _on_press(self, e):
        w=self.winfo_width(); h=self.winfo_height()
        if w<4 or h<4: return
        self.delete('all')
        self._rrect(2,2,w-3,h-3,self._r, fill=self._abg, outline='')
        self.create_text((w-3)//2,(h-3)//2, text=self._t, fill=self._afg, font=self._font, anchor=tk.CENTER)

    def _on_release(self, e):
        self._draw(self._hbg, self._hfg)
        if self._cmd and self._en: self._cmd()

    def configure(self, **kw):
        if 'text' in kw: self._t = kw.pop('text')
        if 'command' in kw: self._cmd = kw.pop('command')
        if 'state' in kw: self._en = (kw.pop('state') != 'disabled')
        super().configure(**kw)
        self._draw(self._bg, self._fg)

# ════════════════════════════════════════════
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("叶子Jinn的刷机工具 v1.0")
        self.root.geometry("1120x850")
        self.root.minsize(1000, 750)
        self.root.configure(bg=C['bg'])
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.is_running = False
        self.current_process = None
        self._cmd_queue = []
        self._queue_lock = threading.Lock()
        self._img_refs = []
        self._setup_styles()
        self._build_ui()
        self.root.after(300, self._check_tools)

    # ── 按钮工厂 ──
    def _btn(self, parent, text, cmd, style='default', width=None, height=36, font=None, **kw):
        styles = {
            'default': dict(bg_color=C['card'], fg_color=C['text'], hover_bg=C['overlay'], hover_fg=C['text'], active_bg=C['blue'], active_fg='#fff', accent=C['accent_dim']),
            'primary': dict(bg_color=C['blue'], fg_color='#fff', hover_bg=C['blue_light'], hover_fg='#fff', active_bg=C['blue_dim'], active_fg='#fff', accent=C['blue_light']),
            'danger': dict(bg_color=C['red'], fg_color='#fff', hover_bg=C['red_light'], hover_fg='#fff', active_bg='#b91c1c', active_fg='#fff', accent='#fff'),
            'green': dict(bg_color=C['green'], fg_color='#fff', hover_bg=C['green_light'], hover_fg='#fff', active_bg='#065f46', active_fg='#fff', accent='#fff'),
            'cyan': dict(bg_color=C['cyan'], fg_color='#fff', hover_bg='#22d3ee', hover_fg='#fff', active_bg='#155e75', active_fg='#fff', accent='#fff'),
            'outline': dict(bg_color=C['surface'], fg_color=C['blue_light'], hover_bg=C['overlay'], hover_fg=C['blue_light'], active_bg=C['blue'], active_fg='#fff', accent=C['blue']),
        }
        s = dict(styles.get(style, styles['default']))
        s.update(kw)
        if font is None:
            font = ('Microsoft YaHei UI', 10, 'bold' if style in ('primary','danger','green','cyan') else 'normal')
        return RoundedButton(parent, text=text, command=cmd, width=width, height=height, font=font, **s)

    def _setup_styles(self):
        s = ttk.Style(); s.theme_use('clam')
        s.configure('.', background=C['bg'], foreground=C['text'], borderwidth=0, font=('Microsoft YaHei UI',10))
        s.configure('TFrame', background=C['bg'])
        s.configure('TLabel', background=C['bg'], foreground=C['text'])
        s.configure('Title.TLabel', background=C['bg'], foreground=C['blue'], font=('Microsoft YaHei UI',18,'bold'))
        s.configure('Sub.TLabel', background=C['bg'], foreground=C['subtext'], font=('Microsoft YaHei UI',9))
        s.configure('Section.TLabel', background=C['bg'], foreground=C['yellow'], font=('Microsoft YaHei UI',10,'bold'))
        # 标签页 - 现代简约 (选中态底部线条模拟)
        s.configure('TNotebook', background=C['bg'], borderwidth=0, tabmargins=[0,0,0,0])
        s.configure('TNotebook.Tab', background=C['surface'], foreground=C['subtext'],
                     padding=[24,12], font=('Microsoft YaHei UI',10,'bold'), borderwidth=0)
        s.map('TNotebook.Tab',
              background=[('selected', C['card']), ('active', C['overlay'])],
              foreground=[('selected', C['blue_light']), ('active', C['text'])])
        # 输入框 - 深色背景+聚焦高亮
        s.configure('TEntry', fieldbackground=C['dark'], foreground=C['text'],
                     insertcolor=C['blue'], borderwidth=2, relief='flat', padding=6)
        s.map('TEntry', fieldbackground=[('focus', '#0a0a16')], bordercolor=[('focus', C['blue'])])
        # 单选框/复选框
        s.configure('TRadiobutton', background=C['bg'], foreground=C['text'], font=('Microsoft YaHei UI',10), focuscolor=C['bg'])
        s.map('TRadiobutton', background=[('active',C['bg'])], foreground=[('active',C['blue_light'])])
        # 复选框 (投屏页)
        s.configure('TCheckbutton', background=C['bg'], foreground=C['text'], font=('Microsoft YaHei UI',10), focuscolor=C['bg'])
        s.map('TCheckbutton', background=[('active',C['bg'])], foreground=[('active',C['blue_light'])])
        # 框架 - 半透明圆角效果 (tkinter LabelFrame不支持圆角, 用groove模拟)
        s.configure('TLabelframe', background=C['bg'], foreground=C['blue_light'], borderwidth=2, relief='groove')
        s.configure('TLabelframe.Label', background=C['bg'], foreground=C['blue_light'], font=('Microsoft YaHei UI',10,'bold'))
        s.configure('TSeparator', background=C['border'])
        # 滚动条 - 更窄更精致
        s.configure('Vertical.TScrollbar', background=C['card'], troughcolor=C['bg'], bordercolor=C['bg'], arrowcolor=C['subtext'], borderwidth=0, width=10)

    def _build_ui(self):
        # ── 标题栏 (卡片+底部光晕线) ──
        hdr = tk.Frame(self.root, bg=C['surface'], height=54)
        hdr.pack(fill=tk.X, padx=12, pady=(10,4)); hdr.pack_propagate(False)
        # 底部双重线条: 细光晕 + 强调色
        tk.Frame(hdr, bg=C['accent_dim'], height=2).pack(side=tk.BOTTOM, fill=tk.X)
        tk.Frame(hdr, bg=C['accent'], height=1, width=200).pack(side=tk.BOTTOM, anchor=tk.W)
        tk.Label(hdr, text="  叶子Jinn的刷机工具", bg=C['surface'], fg=C['blue'], font=('Microsoft YaHei UI',18,'bold')).pack(side=tk.LEFT, padx=14, pady=6)
        tk.Label(hdr, text="v1.0", bg=C['surface'], fg=C['subtext'], font=('Microsoft YaHei UI',10)).pack(side=tk.LEFT, padx=(2,0))
        # 管理员指示器 (卡片式)
        af = tk.Frame(hdr, bg=C['bg'], highlightbackground=C['border'], highlightthickness=1); af.pack(side=tk.RIGHT, padx=14)
        ac = '管理员' if is_admin() else '非管理员'; cl = C['green'] if is_admin() else C['red']
        tk.Label(af, text="●", bg=C['bg'], fg=cl, font=('Microsoft YaHei UI',8)).pack(side=tk.LEFT, padx=(6,2), pady=3)
        tk.Label(af, text=ac, bg=C['bg'], fg=cl, font=('Microsoft YaHei UI',9,'bold')).pack(side=tk.LEFT, padx=(0,8), pady=3)

        # ── Notebook ──
        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4,4))
        self._tab_device(nb); self._tab_magisk(nb); self._tab_recovery(nb)
        self._tab_files(nb); self._tab_advanced(nb); self._tab_tools(nb); self._tab_screen(nb)
        ttk.Separator(self.root).pack(fill=tk.X, padx=12, pady=4)

        # ── 底部: 左输出+右图片 ──
        bottom = tk.Frame(self.root, bg=C['bg'])
        bottom.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0,4))

        # 左: 命令输出 (卡片+渐变感)
        of = tk.Frame(bottom, bg=C['card'], highlightbackground=C['border'], highlightthickness=1)
        of.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,6))
        oh = tk.Frame(of, bg=C['card']); oh.pack(fill=tk.X, padx=10, pady=(8,2))
        tk.Label(oh, text="▸ 命令输出", bg=C['card'], fg=C['blue_light'], font=('Microsoft YaHei UI',10,'bold')).pack(side=tk.LEFT)
        bh = tk.Frame(oh, bg=C['card']); bh.pack(side=tk.RIGHT)
        self._btn(bh, "终止命令", self._kill_cmd, 'danger', width=90, height=30).pack(side=tk.LEFT, padx=2)
        self._btn(bh, "清空", self._clear_log, width=65, height=30).pack(side=tk.LEFT, padx=2)

        tf = tk.Frame(of, bg=C['dark'], highlightbackground=C['border'], highlightthickness=1)
        tf.pack(fill=tk.BOTH, expand=True, padx=10, pady=(2,8))
        self.output = scrolledtext.ScrolledText(tf, bg=C['dark'], fg=C['text'], font=('Consolas',10),
            insertbackground=C['text'], selectbackground=C['overlay'], relief='flat', wrap=tk.WORD, borderwidth=6, highlightthickness=0)
        self.output.pack(fill=tk.BOTH, expand=True)
        self.output.configure(state=tk.DISABLED)
        for tag,clr in [('cmd',C['blue']),('ok',C['green']),('warn',C['yellow']),('err',C['red']),('info',C['text'])]:
            self.output.tag_configure(tag, foreground=clr)

        # 右: 二维码
        self._build_qrcode(bottom)

        # ── 状态栏 (卡片式) ──
        sbar = tk.Frame(self.root, bg=C['surface'], height=34, highlightbackground=C['border'], highlightthickness=1)
        sbar.pack(fill=tk.X, padx=12, pady=(4,10)); sbar.pack_propagate(False)
        self.status = tk.Label(sbar, text="就绪", bg=C['surface'], fg=C['text'], font=('Microsoft YaHei UI',9), anchor=tk.W)
        self.status.pack(side=tk.LEFT, padx=14, pady=4)
        tk.Frame(sbar, bg=C['border'], width=1, height=20).pack(side=tk.LEFT)
        self.tool_status = tk.Label(sbar, text="", bg=C['surface'], fg=C['subtext'], font=('Microsoft YaHei UI',9,'bold'), anchor=tk.E)
        self.tool_status.pack(side=tk.RIGHT, padx=14, pady=4)

    def _load_photo(self, fn):
        """加载图片: 外部原图(.png)优先, 否则解密内置 .enc, 全程内存操作"""
        p = xiaomi_path(fn)
        if p.exists():
            return tk.PhotoImage(file=str(p))
        enc = BUNDLE_DIR / 'XiaoMi' / (fn + _IMG_ENC_SUFFIX)
        if enc.exists():
            data = img_xor(enc.read_bytes(), fn)
            return tk.PhotoImage(data=base64.b64encode(data).decode('ascii'))
        return None

    def _build_qrcode(self, parent):
        right = tk.Frame(parent, bg=C['card'], width=360, highlightbackground=C['border'], highlightthickness=1)
        right.pack(side=tk.LEFT, fill=tk.BOTH, padx=(6,0)); right.pack_propagate(False)

        # 4张图片 2x2 网格均匀分布
        items = [
            ("_wxpay_thumb.png",  "微信收款", "微信收款.png"),
            ("_alipay_thumb.png", "支付宝收款", "支付宝收款.png"),
            ("_wxfriend_thumb.png","微信好友", "微信好友.png"),
            ("_qqfriend_thumb.png","QQ好友",   "QQ好友.png"),
        ]
        for idx, (thumb, label, orig) in enumerate(items):
            img = self._load_photo(thumb)
            if img is None: continue
            try:
                r = int(idx / 2); c = idx % 2
                cell = tk.Frame(right, bg=C['card'], highlightbackground=C['border'], highlightthickness=1)
                cell.grid(row=r, column=c, sticky='nsew', padx=3, pady=3)
                right.grid_rowconfigure(r, weight=1)
                right.grid_columnconfigure(c, weight=1)
                self._img_refs.append(img)
                tk.Label(cell, image=img, bg=C['card']).pack(pady=(6,0))
                bf = tk.Frame(cell, bg=C['card']); bf.pack(fill=tk.X, pady=(2,4))
                tk.Label(bf, text=label, bg=C['card'], fg=C['subtext'], font=('Microsoft YaHei UI',9)).pack(side=tk.LEFT, padx=4)
                self._btn(bf, "大图", lambda o=orig: self._view_large(o), width=56, height=26, font=('Microsoft YaHei UI',8)).pack(side=tk.RIGHT, padx=4)
            except:
                pass

    def _view_large(self, fn):
        img = self._load_photo(fn)
        if img is None: messagebox.showwarning("提示","图片未找到"); return
        win = tk.Toplevel(self.root); win.title("查看大图 - "+os.path.basename(fn)); win.configure(bg=C['bg'])
        win.transient(self.root); win.grab_set()
        try:
            win._photo = img
            w,h = img.width(), img.height()
            sw,sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            mw,mh = int(sw*0.7), int(sh*0.7)
            if w>mw or h>mh:
                r = min(mw/w, mh/h); w,h = int(w*r), int(h*r)
            tk.Label(win, image=img, bg=C['bg']).pack(padx=14, pady=14)
            self._btn(win, "关闭", win.destroy, width=80, height=32).pack(pady=(0,12))
            win.update_idletasks()
            win.geometry(f"{w}x{h+70}+{(sw-w)//2}+{(sh-h-70)//2}")
        except Exception as e:
            messagebox.showerror("错误", str(e)); win.destroy()

    # ── 工具方法 ──
    def _log(self, t, tag='info'):
        self.output.configure(state=tk.NORMAL)
        self.output.insert(tk.END, t+'\n', tag)
        self.output.see(tk.END); self.output.configure(state=tk.DISABLED)
    def _set_status(self, t): self.status.configure(text=t)

    def _check_tools(self):
        a,f = os.path.exists(get_tool_path('adb')), os.path.exists(get_tool_path('fastboot'))
        self.tool_status.configure(text=f"ADB:[{'OK' if a else 'X'}]  Fastboot:[{'OK' if f else 'X'}]")
        if not (a and f): self._log("[!] adb.exe 或 fastboot.exe 未找到", 'warn')

    def _clear_log(self):
        self.output.configure(state=tk.NORMAL); self.output.delete('1.0', tk.END); self.output.configure(state=tk.DISABLED)

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
        """通用子进程执行 (Popen+readline+after), 消除3处重复
        proc_attr: 存储进程引用的属性名 ('current_process' 或 'scrpcy_process')
        """
        self._log(f">>> {' '.join(os.fspath(c) for c in cmd)}", 'cmd')
        self._set_status(f"执行中: {label}")
        self.is_running = True
        def w():
            try:
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    encoding=SYS_ENCODING, errors='replace', creationflags=subprocess.CREATE_NO_WINDOW)
                setattr(self, proc_attr, p)
                for line in iter(p.stdout.readline, ''):
                    d = line.rstrip() if line else ''
                    if d: self.root.after(0, self._log, d, 'info')
                p.wait(); r = p.returncode
                self.root.after(0, self._log, f"[OK] 完成 (返回码: {r})" if r==0 else f"[!!] 返回码: {r}", 'ok' if r==0 else 'warn')
            except Exception as e: self.root.after(0, self._log, f"[ERR] {e}", 'err')
            finally:
                setattr(self, proc_attr, None); self.is_running = False
                self.root.after(0, self._set_status, "就绪")
                if on_done: self.root.after(0, on_done)
        threading.Thread(target=w, daemon=True).start()

    def _run(self, tool, args):
        """加入命令队列顺序执行"""
        with self._queue_lock:
            self._cmd_queue.append((tool, args))
            if not self.is_running:
                self.root.after(100, self._run_next)  # 等当前帧结束再启动

    def _run_next(self):
        with self._queue_lock:
            if not self._cmd_queue: return
            if self.is_running: return  # 已有命令在执行中
            tool, args = self._cmd_queue.pop(0)
            remaining = bool(self._cmd_queue)
        tp = get_tool_path(tool)
        if tool in BUNDLED_TOOLS and not tp.exists():
            self._log(f"[!] 未找到打包内置工具: {tool}.exe", 'err')
            if remaining: self.root.after(300, self._run_next)
            return
        cmd = [tp] + args
        self._exec_subprocess(cmd, f"{tool} {' '.join(args)}",
                              on_done=(lambda: self.root.after(300, self._run_next)) if remaining else None)

    def _run_file(self, fp, args=None):
        """执行本地exe/bat/ps1文件 (参数数组, 不经过CMD字符串拼接)"""
        fp = Path(fp)
        if not fp.exists():
            self._log(f"[!] 文件未找到: {fp}", 'warn')
            messagebox.showwarning("提示", f"文件未找到:\n{fp}"); return
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
        if mode == 'dir':
            return filedialog.askdirectory(title=title, initialdir=str(BASE_DIR))
        if mode == 'save':
            e = ext or '.img'
            return filedialog.asksaveasfilename(title=title, defaultextension=e, initialdir=str(BASE_DIR),
                                                filetypes=[("镜像文件", f"*{e}"), ("所有文件", "*.*")])
        if mode == 'any':
            return filedialog.askopenfilename(title=title, initialdir=str(BASE_DIR), filetypes=[("所有文件", "*.*")])
        if ext:
            return filedialog.askopenfilename(title=title, initialdir=str(BASE_DIR),
                                              filetypes=[(f"{ext.upper()}文件", f"*{ext}"), ("所有文件", "*.*")])
        return filedialog.askopenfilename(title=title, initialdir=str(BASE_DIR),
                                          filetypes=[("镜像文件", "*.img"), ("所有文件", "*.*")])

    def _on_close(self):
        # 终止正在执行的命令和投屏进程
        for p in [self.current_process, getattr(self, 'scrpcy_process', None)]:
            if p:
                try: p.terminate()
                except: pass
        # 强制结束ADB/Fastboot/Scrcpy进程(释放临时目录文件句柄, 避免PyInstaller清理失败弹窗)
        for exe in ['adb.exe','fastboot.exe','scrcpy.exe']:
            try: subprocess.run(['taskkill','/f','/im',exe], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            except: pass
        self.root.destroy()

    # ════════════════════════════════════════════
    # Tab 1: 设备信息
    # ════════════════════════════════════════════
    def _tab_device(self, nb):
        ot = ttk.Frame(nb); nb.add(ot, text="  设备信息  ")
        cv = tk.Canvas(ot, bg=C['bg'], highlightthickness=0)
        sb = ttk.Scrollbar(ot, orient="vertical", command=cv.yview)
        tab = ttk.Frame(cv)
        tab.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0,0), window=tab, anchor="nw")
        cv.configure(yscrollcommand=sb.set); cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.pack(side=tk.RIGHT, fill=tk.Y)
        def _on_mw(e, c=cv): c.yview_scroll(int(-1*(e.delta/120)), "units")
        cv.bind("<MouseWheel>", _on_mw, add="+")
        # 当鼠标在滚动条上时不触发
        sb.bind("<MouseWheel>", lambda e: None)

        f1=ttk.LabelFrame(tab, text="ADB 设备信息 (手机需开启USB调试)"); f1.pack(fill=tk.X, padx=18, pady=(10,5))
        r1=ttk.Frame(f1); r1.pack(fill=tk.X, padx=12, pady=6)
        for t,x,a in [("检测ADB设备","adb",["devices"]),("查看机型","adb",["shell","getprop","ro.product.name"]),("查看内核","adb",["shell","uname","-r"])]:
            self._btn(r1, t, lambda x=x,a=a: self._run(x,a), width=140).pack(side=tk.LEFT, padx=4)

        f2=ttk.LabelFrame(tab, text="Fastboot 设备信息 (手机需在Fastboot模式)"); f2.pack(fill=tk.X, padx=18, pady=5)
        r2=ttk.Frame(f2); r2.pack(fill=tk.X, padx=12, pady=6)
        for t,x,a in [("检测设备","fastboot",["devices"]),("查看机型","fastboot",["getvar","product"]),("查看Slot","fastboot",["getvar","current-slot"])]:
            self._btn(r2, t, lambda x=x,a=a: self._run(x,a), width=120).pack(side=tk.LEFT, padx=4)
        r2b=ttk.Frame(f2); r2b.pack(fill=tk.X, padx=12, pady=(0,6))
        for t,x,a in [("BL锁(骁龙)","fastboot",["oem","device-info"]),("BL锁(天玑)","fastboot",["oem","lks"])]:
            self._btn(r2b, t, lambda x=x,a=a: self._run(x,a), width=125).pack(side=tk.LEFT, padx=4)

        f3=ttk.LabelFrame(tab, text="重启操作"); f3.pack(fill=tk.X, padx=18, pady=5)
        r3=ttk.Frame(f3); r3.pack(fill=tk.X, padx=12, pady=6)
        for t,x,a in [("重启到Fastboot","adb",["reboot","bootloader"]),("重启到Recovery","fastboot",["reboot","recovery"])]:
            self._btn(r3, t, lambda x=x,a=a: self._run(x,a), width=150).pack(side=tk.LEFT, padx=4)
        self._btn(r3, "重启系统", self._reboot_both, width=150).pack(side=tk.LEFT, padx=4)

    def _reboot_both(self):
        """先adb reboot, 再接fastboot reboot"""
        self._run("adb",["reboot"])
        self._run("fastboot",["reboot"])

    # ════════════════════════════════════════════
    # Tab 2: 刷入面具
    # ════════════════════════════════════════════
    def _tab_magisk(self, nb):
        tab=ttk.Frame(nb); nb.add(tab, text="  刷入面具  ")
        ttk.Label(tab, text="将Magisk/KernelSU镜像刷入boot分区以获取ROOT权限", style='Sub.TLabel').pack(padx=18,pady=(10,4),anchor=tk.W)
        sf=ttk.Frame(tab); sf.pack(fill=tk.X, padx=18, pady=3)
        ttk.Label(sf, text="镜像文件:").pack(side=tk.LEFT)
        self.magisk_var=tk.StringVar(value=str(BASE_DIR / "2.img")); ttk.Entry(sf,textvariable=self.magisk_var,width=55).pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)
        self._btn(sf, "浏览...", self._sel_magisk, width=78, height=32).pack(side=tk.LEFT)
        ff=ttk.LabelFrame(tab, text="刷入方式"); ff.pack(fill=tk.X, padx=18, pady=6)
        self.flash_method=tk.StringVar(value="boot")
        for t,v in [("flash boot (865-)","boot"),("flash init_boot (870+)","init_boot"),("flash init_boot_ab (K60Ultra)","init_boot_ab")]:
            ttk.Radiobutton(ff,text=t,variable=self.flash_method,value=v).pack(anchor=tk.W,padx=18,pady=2)
        bf=ttk.Frame(tab); bf.pack(fill=tk.X, padx=18, pady=5)
        self._btn(bf, "开始刷入", self._do_flash_magisk, 'primary', width=115).pack(side=tk.LEFT, padx=4)
        self._btn(bf, "重启系统", lambda: self._run("fastboot",["reboot"]), width=100).pack(side=tk.LEFT, padx=4)
        ttk.Separator(tab).pack(fill=tk.X, padx=18, pady=6)
        ttk.Label(tab, text="从手机拉取boot镜像", style='Section.TLabel').pack(padx=18, pady=(4,2), anchor=tk.W)
        pf1=ttk.Frame(tab); pf1.pack(fill=tk.X, padx=18, pady=3)
        ttk.Label(pf1, text="手机路径:").pack(side=tk.LEFT)
        self.pull_boot_src=tk.StringVar(value="/storage/emulated/0/Download/2.img"); ttk.Entry(pf1,textvariable=self.pull_boot_src).pack(side=tk.LEFT,padx=6,fill=tk.X,expand=True)
        pf2=ttk.Frame(tab); pf2.pack(fill=tk.X, padx=18, pady=3)
        ttk.Label(pf2, text="保存到:").pack(side=tk.LEFT)
        self.pull_boot_dst=tk.StringVar(value=str(BASE_DIR / "2.img")); ttk.Entry(pf2,textvariable=self.pull_boot_dst).pack(side=tk.LEFT,padx=6,fill=tk.X,expand=True)
        self._btn(pf2, "浏览...", self._sel_pull_boot_dst, width=78, height=32).pack(side=tk.LEFT)
        self._btn(pf2, "拉取", self._do_pull_boot, 'primary', width=105).pack(side=tk.LEFT, padx=4)

    def _sel_magisk(self):
        p=self._browse("选择img镜像")
        if p: self.magisk_var.set(p)
    def _sel_pull_boot_dst(self):
        p=self._browse("保存boot镜像", mode='save')
        if p: self.pull_boot_dst.set(p)
    def _do_flash_magisk(self):
        img=self.magisk_var.get().strip()
        if not img or not os.path.exists(img): messagebox.showwarning("提示","请先选择有效的镜像文件"); return
        self._run("fastboot",["flash",self.flash_method.get(),img])
    def _do_pull_boot(self):
        s=self.pull_boot_src.get().strip(); d=self.pull_boot_dst.get().strip()
        if not d: messagebox.showwarning("提示","请填写保存路径"); return
        self._run("adb",["pull",s,d])

    # ════════════════════════════════════════════
    # Tab 3: 刷Recovery
    # ════════════════════════════════════════════
    def _tab_recovery(self, nb):
        tab=ttk.Frame(nb); nb.add(tab, text="  刷Recovery  ")
        ttk.Label(tab, text="刷入Recovery镜像 (TWRP等)", style='Sub.TLabel').pack(padx=18,pady=(10,4),anchor=tk.W)
        sf=ttk.Frame(tab); sf.pack(fill=tk.X, padx=18, pady=3)
        ttk.Label(sf, text="Recovery镜像:").pack(side=tk.LEFT)
        self.recov_var=tk.StringVar(); ttk.Entry(sf,textvariable=self.recov_var,width=55).pack(side=tk.LEFT,padx=6,fill=tk.X,expand=True)
        self._btn(sf, "浏览...", self._sel_recov, width=78, height=32).pack(side=tk.LEFT)
        ff=ttk.LabelFrame(tab, text="刷入方式"); ff.pack(fill=tk.X, padx=18, pady=6)
        self.recov_method=tk.StringVar(value="recovery_only")
        for t,v in [("仅刷recovery (骁龙865-)","recovery_only"),("刷recovery_a + recovery_b (骁龙8G+)","recovery_ab"),("刷misc.bin + recovery (骁龙855-)","misc_recovery"),("临时启动 (不写入)","boot_temp")]:
            ttk.Radiobutton(ff,text=t,variable=self.recov_method,value=v).pack(anchor=tk.W,padx=18,pady=2)
        bf=ttk.Frame(tab); bf.pack(fill=tk.X, padx=18, pady=5)
        self._btn(bf, "开始刷入", self._do_flash_recov, 'primary', width=150).pack(side=tk.LEFT, padx=4)
        self._btn(bf, "重启进入Recovery", lambda: self._run("fastboot",["reboot","recovery"]), width=150).pack(side=tk.LEFT, padx=4)

    def _sel_recov(self):
        p=self._browse("选择Recovery镜像")
        if p: self.recov_var.set(p)
    def _do_flash_recov(self):
        img=self.recov_var.get().strip()
        if not img or not os.path.exists(img): messagebox.showwarning("提示","请先选择Recovery镜像"); return
        m=self.recov_method.get()
        if m=="recovery_only": self._run("fastboot",["flash","recovery",img])
        elif m=="recovery_ab":
            self._run("fastboot",["flash","recovery_a",img]); self._run("fastboot",["flash","recovery_b",img])
        elif m=="misc_recovery":
            misc=resource_path("misc.bin")
            if misc.exists(): self._run("fastboot",["flash","misc",misc])
            else: self._log("[!] misc.bin未找到, 跳过misc刷入",'warn')
            self._run("fastboot",["flash","recovery",img])
        elif m=="boot_temp": self._run("fastboot",["boot",img])

    # ════════════════════════════════════════════
    # Tab 4: 文件管理
    # ════════════════════════════════════════════
    def _tab_files(self, nb):
        tab=ttk.Frame(nb); nb.add(tab, text="  文件管理  ")
        f1=ttk.LabelFrame(tab, text="安装APK"); f1.pack(fill=tk.X, padx=18, pady=(10,5))
        r1=ttk.Frame(f1); r1.pack(fill=tk.X, padx=12, pady=6)
        ttk.Label(r1, text="APK:").pack(side=tk.LEFT)
        self.apk_var=tk.StringVar(); ttk.Entry(r1,textvariable=self.apk_var,width=50).pack(side=tk.LEFT,padx=6,fill=tk.X,expand=True)
        self._btn(r1, "浏览...", self._sel_apk, width=78, height=32).pack(side=tk.LEFT)
        self._btn(r1, "安装", self._do_install_apk, 'green', width=105).pack(side=tk.LEFT, padx=4)

        f2=ttk.LabelFrame(tab, text="推送到手机 (adb push)"); f2.pack(fill=tk.X, padx=18, pady=5)
        r2a=ttk.Frame(f2); r2a.pack(fill=tk.X, padx=12, pady=4)
        ttk.Label(r2a, text="取电脑文件:").pack(side=tk.LEFT)
        self.push_src=tk.StringVar(); ttk.Entry(r2a,textvariable=self.push_src,width=45).pack(side=tk.LEFT,padx=6,fill=tk.X,expand=True)
        self._btn(r2a, "文件", self._sel_push_src, width=85, height=30).pack(side=tk.LEFT)
        self._btn(r2a, "文件夹", self._sel_push_dir, width=85, height=30).pack(side=tk.LEFT)
        r2b=ttk.Frame(f2); r2b.pack(fill=tk.X, padx=12, pady=4)
        ttk.Label(r2b, text="存手机路径:").pack(side=tk.LEFT)
        self.push_dst=tk.StringVar(value="/storage/emulated/0/"); ttk.Entry(r2b,textvariable=self.push_dst,width=55).pack(side=tk.LEFT,padx=6,fill=tk.X,expand=True)
        self._btn(r2b, "推送", self._do_push, 'primary', width=105).pack(side=tk.LEFT, padx=4)

        f3=ttk.LabelFrame(tab, text="从手机拉取文件 (adb pull)"); f3.pack(fill=tk.X, padx=18, pady=5)
        r3a=ttk.Frame(f3); r3a.pack(fill=tk.X, padx=12, pady=4)
        ttk.Label(r3a, text="取手机文件:").pack(side=tk.LEFT)
        self.pull_src=tk.StringVar(value="/storage/emulated/0/Download/2.img"); ttk.Entry(r3a,textvariable=self.pull_src,width=45).pack(side=tk.LEFT,padx=6,fill=tk.X,expand=True)
        r3b=ttk.Frame(f3); r3b.pack(fill=tk.X, padx=12, pady=4)
        ttk.Label(r3b, text="存电脑路径:").pack(side=tk.LEFT)
        self.pull_dst=tk.StringVar(value=str(BASE_DIR)); ttk.Entry(r3b,textvariable=self.pull_dst,width=45).pack(side=tk.LEFT,padx=6,fill=tk.X,expand=True)
        self._btn(r3b, "浏览...", self._sel_pull_dst, width=78, height=32).pack(side=tk.LEFT)
        self._btn(r3b, "拉取", self._do_pull, 'primary', width=105).pack(side=tk.LEFT, padx=4)

    def _sel_apk(self):
        p=self._browse("选择APK", ext='.apk')
        if p: self.apk_var.set(p)
    def _sel_push_src(self):
        p=self._browse("选择文件", mode='any')
        if p: self.push_src.set(p)
    def _sel_push_dir(self):
        p=self._browse("选择文件夹", mode='dir')
        if p: self.push_src.set(p)
    def _sel_pull_dst(self):
        p=self._browse("选择保存目录", mode='dir')
        if p: self.pull_dst.set(p)
    def _do_install_apk(self):
        a=self.apk_var.get().strip()
        if not a or not os.path.exists(a): messagebox.showwarning("提示","请选择APK文件"); return
        # 直接传Unicode路径: adb经CreateProcessW(参数数组)原生支持中文, 短路径反而会变中文+~1乱码
        self._run("adb",["install",a])
    def _do_push(self):
        s,d=self.push_src.get().strip(),self.push_dst.get().strip()
        if not s or not os.path.exists(s): messagebox.showwarning("提示","请选择源文件"); return
        if not d: messagebox.showwarning("提示","请填写手机路径"); return
        # 目录目标显式拼上文件名 (Android16等设备adbd目录探测失效→EISDIR)
        d = _join_remote_target(d, os.path.basename(s.rstrip('/\\')))
        self._run("adb",["push",s,d])
    def _do_pull(self):
        s,d=self.pull_src.get().strip(),self.pull_dst.get().strip()
        if not s or not d: messagebox.showwarning("提示","请填写路径"); return
        # pull到本地目录时adb会自行算文件名并截断中文, 显式拼上远程文件名
        if os.path.isdir(d):
            d = os.path.join(d, os.path.basename(s.rstrip('/')))
        self._run("adb",["pull",s,d])

    # ════════════════════════════════════════════
    # Tab 5: 高级功能
    # ════════════════════════════════════════════
    def _tab_advanced(self, nb):
        tab=ttk.Frame(nb); nb.add(tab, text="  高级功能  ")
        r1=ttk.Frame(tab); r1.pack(fill=tk.X, padx=18, pady=(10,4))
        self._btn(r1, "执行BL解锁", lambda:self._run("fastboot",["flashing","unlock"]), 'danger', width=175).pack(side=tk.LEFT, padx=4)
        self._btn(r1, "修复hosts加速下载", self._fix_hosts, width=175).pack(side=tk.LEFT, padx=4)
        self._btn(r1, "修复USB驱动注册表", self._fix_usb, width=175).pack(side=tk.LEFT, padx=4)
        self._btn(r1, "刷新DNS缓存", lambda:self._run("ipconfig",["/flushdns"]), width=175).pack(side=tk.LEFT, padx=4)
        r2=ttk.Frame(tab); r2.pack(fill=tk.X, padx=18, pady=4)
        ttk.Label(r2, text="vbmeta:").pack(side=tk.LEFT)
        self.vbmeta_var=tk.StringVar(); ttk.Entry(r2,textvariable=self.vbmeta_var,width=35).pack(side=tk.LEFT,padx=4,fill=tk.X,expand=True)
        self._btn(r2, "浏览...", self._sel_vbmeta, width=78, height=32).pack(side=tk.LEFT)
        self._btn(r2, "刷入(禁用验证)", self._do_vbmeta, 'primary', width=150).pack(side=tk.LEFT, padx=4)
        r3=ttk.Frame(tab); r3.pack(fill=tk.X, padx=18, pady=4)
        ttk.Label(r3, text="自定义命令:").pack(side=tk.LEFT)
        self.cmd_var=tk.StringVar(); ttk.Entry(r3,textvariable=self.cmd_var).pack(side=tk.LEFT,padx=6,fill=tk.X,expand=True)
        self._btn(r3, "执行", self._do_custom, 'primary').pack(side=tk.LEFT, padx=4)
        r4=ttk.Frame(tab); r4.pack(fill=tk.X, padx=18, pady=4)
        self._btn(r4, "快捷命令参考", self._open_quick_cmd, 'outline').pack(side=tk.LEFT, padx=4)

    def _sel_vbmeta(self):
        p=self._browse("选择vbmeta镜像")
        if p: self.vbmeta_var.set(p)
    def _do_vbmeta(self):
        img=self.vbmeta_var.get().strip()
        if not img or not os.path.exists(img): messagebox.showwarning("提示","请选择vbmeta镜像"); return
        self._run("fastboot",["--disable-verity","--disable-verification","flash","vbmeta",img])
    def _do_custom(self):
        s=self.cmd_var.get().strip()
        if not s: return
        try:
            p=shlex.split(s)
            if not p: return
            self._run(p[0],p[1:])
        except Exception as e:
            self._log(f"[ERR] 命令解析失败: {e}", 'err')

    def _open_quick_cmd(self):
        c="""B站：叶子Jinn

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
        win=tk.Toplevel(self.root); win.title("快捷命令参考"); win.configure(bg=C['bg']); win.geometry("620x520")
        win.transient(self.root); win.grab_set()
        tk.Label(win, text="常用命令参考", bg=C['bg'], fg=C['yellow'], font=('Microsoft YaHei UI',12,'bold')).pack(pady=(10,6))
        txt=scrolledtext.ScrolledText(win,bg=C['dark'],fg=C['text'],font=('Consolas',10),wrap=tk.WORD,borderwidth=0,highlightthickness=0)
        txt.pack(fill=tk.BOTH,expand=True,padx=14,pady=6); txt.insert(tk.END,c); txt.configure(state=tk.DISABLED)
        self._btn(win, "关闭", win.destroy, width=80, height=32).pack(pady=(0,12))

    def _fix_hosts(self):
        if not is_admin(): messagebox.showerror("错误","需要管理员权限!"); return
        try:
            hp = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'System32' / 'drivers' / 'etc' / 'hosts'
            with open(hp,'r',encoding='utf-8',errors='ignore') as f: c=f.read()
            if 'bigota.d.miui.com' in c: self._log("[OK] hosts已包含小米节点",'ok'); return
            with open(hp,'a',encoding='utf-8') as f: f.write("\n#小米刷机包下载加速\n47.74.196.250 bigota.d.miui.com\n47.74.196.250 hugeota.d.miui.com\n")
            self._log("[OK] hosts已更新",'ok'); self._run("ipconfig",["/flushdns"])
        except Exception as e: self._log(f"[ERR] {e}",'err')

    def _fix_usb(self):
        if not is_admin(): messagebox.showerror("错误","需要管理员权限!"); return
        self._log("[*] 开始修复USB驱动注册表...",'info')
        for n,v in [("osvc","0000"),("SkipContainerIdQuery","01000000"),("SkipBOSDescriptorQuery","01000000")]:
            try:
                r=subprocess.run(['reg','add',r'HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\usbflags\18D1D00D0100','/v',n,'/t','REG_BINARY','/d',v,'/f'],
                    capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
                if r.returncode==0: self._log(f"[OK] 注册表已写入: {n}",'ok')
                else: self._log(f"[!!] 注册表写入失败: {n} - {r.stderr.strip()}",'warn')
            except Exception as e: self._log(f"[ERR] 注册表写入异常: {e}",'err')
        self._log("[OK] USB驱动注册表修复完成",'ok')

    # ════════════════════════════════════════════
    # Tab 6: 实用工具
    # ════════════════════════════════════════════
    def _tab_tools(self, nb):
        tab=ttk.Frame(nb); nb.add(tab, text="  实用工具  ")
        # 6个按钮 3x2 网格, 统一宽度150
        rows = [ttk.Frame(tab) for _ in range(2)]
        for i, r in enumerate(rows):
            r.pack(fill=tk.X, padx=18, pady=(10 if i==0 else 4, 4))
        btns = [
            ("设备管理器", self._open_devmgmt, 'default'),
            ("安卓的驱动", lambda:self._run_file(xiaomi_path("OPPO.exe")), 'primary'),
            ("内存清理 (Cleaner)", lambda:self._run_file(xiaomi_path("WinMemoryCleaner.exe")), 'green'),
            ("安装压缩工具 (Bandizip)", lambda:self._run_file(xiaomi_path("Bandizipv6.29.exe")), 'primary'),
            ("关闭UA警告 (bat)", lambda:self._run_file(xiaomi_path("DisableAllFileWarnings.bat")), 'default'),
            ("关闭UA警告 (ps1)", lambda:self._run_file(xiaomi_path("DisableAllFileWarnings.ps1")), 'default'),
        ]
        for i, (txt, cmd, st) in enumerate(btns):
            self._btn(rows[i//3], txt, cmd, st, width=150, height=34).pack(side=tk.LEFT, padx=6, expand=True, fill=tk.X)

    def _open_devmgmt(self):
        self._log(">>> 打开设备管理器",'cmd')
        try: os.startfile('devmgmt.msc'); self._log("[OK] 设备管理器已打开",'ok')
        except Exception as e: self._log(f"[ERR] {e}",'err')

    # ════════════════════════════════════════════
    # Tab 7: 投屏控制
    # ════════════════════════════════════════════
    def _tab_screen(self, nb):
        tab=ttk.Frame(nb); nb.add(tab, text="  投屏控制  ")
        self.scrpcy_process=None
        self._device_serial=None  # 当前设备序列号
        
        r1=ttk.Frame(tab); r1.pack(fill=tk.X, padx=18, pady=(12,6))
        self._btn(r1, "开始投屏", self._start_scrcpy, 'green', width=140, height=40).pack(side=tk.LEFT, padx=5)
        self._btn(r1, "结束投屏", self._stop_scrcpy, 'danger', width=140, height=40).pack(side=tk.LEFT, padx=5)
        self._btn(r1, "结束ADB进程", lambda:self._run("adb",["kill-server"]), width=140, height=40).pack(side=tk.LEFT, padx=5)
        
        # 新增: 自动息屏勾选框
        self.auto_screen_off=tk.BooleanVar(value=False)  # 默认不勾选
        ttk.Checkbutton(tab, text="自动息屏 (投屏时关闭手机屏幕)", variable=self.auto_screen_off,
                        style='TRadiobutton').pack(anchor=tk.W, padx=18, pady=4)
        
        ttk.Label(tab, text="投屏参数:", style='Section.TLabel').pack(anchor=tk.W, padx=18, pady=(6,2))
        r2=ttk.Frame(tab); r2.pack(fill=tk.X, padx=18, pady=4)
        self.scrpy_bitrate=tk.StringVar(value="8000000")
        ttk.Label(r2, text="码率:").pack(side=tk.LEFT)
        ttk.Entry(r2,textvariable=self.scrpy_bitrate,width=10).pack(side=tk.LEFT, padx=4)
        ttk.Label(r2, text="(默认8M, 越高越清晰)").pack(side=tk.LEFT, padx=6)
        self.scrpy_maxsize=tk.StringVar(value="0")
        ttk.Label(r2, text="  分辨率上限:").pack(side=tk.LEFT)
        ttk.Entry(r2,textvariable=self.scrpy_maxsize,width=6).pack(side=tk.LEFT, padx=4)
        ttk.Label(r2, text="(0=原尺寸)").pack(side=tk.LEFT)
        ttk.Separator(tab).pack(fill=tk.X, padx=18, pady=8)
        ttk.Label(tab, text="手机导航键 (鼠标点击):", style='Section.TLabel').pack(anchor=tk.W, padx=18)
        r3=ttk.Frame(tab); r3.pack(fill=tk.X, padx=18, pady=8)
        for l,c in [("← 返回",4),("■ 主页",3),("□ 后台",187)]:
            self._btn(r3, l, lambda c=c: self._adb_key(c), 'primary', width=110, height=36).pack(side=tk.LEFT, padx=6)
        ttk.Separator(tab).pack(fill=tk.X, padx=18, pady=5)
        ttk.Label(tab, text="其他快捷操作:", style='Section.TLabel').pack(anchor=tk.W, padx=18)
        r4=ttk.Frame(tab); r4.pack(fill=tk.X, padx=18, pady=6)
        for l,c in [("电源",26),("音量+",24),("音量-",25),("截图",276),("展开通知栏",83)]:
            self._btn(r4, l, lambda c=c: self._adb_key(c), width=105, height=34).pack(side=tk.LEFT, padx=4)

    def _get_device_serial(self):
        """获取当前连接的设备序列号"""
        adb=get_tool_path('adb')
        if not adb.exists():
            self._log("[!] 未找到打包内置 adb.exe", 'err')
            return None
        try:
            r=subprocess.run([adb,'devices','-l'], capture_output=True, text=True,
                             encoding=SYS_ENCODING, errors='replace', creationflags=subprocess.CREATE_NO_WINDOW)
            lines=r.stdout.strip().split('\n')
            devices=[]
            for line in lines[1:]:  # 跳过标题行
                if line.strip() and 'device' in line:
                    parts=line.split()
                    if parts:
                        devices.append(parts[0])  # 序列号
            if len(devices)==0:
                return None
            if len(devices)==1:
                return devices[0]
            # 多设备: 返回第一个(或让用户选择)
            self._log(f"[!] 检测到 {len(devices)} 个设备: {', '.join(devices)}", 'warn')
            return devices[0]  # 默认用第一个
        except Exception as e:
            self._log(f"[ERR] 获取设备序列号失败: {e}", 'err')
            return None

    def _start_scrcpy(self):
        sp=get_tool_path('scrcpy')
        if not os.path.exists(sp): messagebox.showwarning("提示","scrcpy.exe 未找到"); return
        
        # 获取设备序列号 (用独立subprocess.run, 不经过队列)
        self._device_serial=self._get_device_serial()
        if not self._device_serial:
            messagebox.showwarning("提示","未检测到ADB设备，请确保手机已连接并开启USB调试")
            return
        
        self._log(f"[OK] 设备序列号: {self._device_serial}", 'ok')
        
        br=self.scrpy_bitrate.get().strip() or "8000000"
        ms=self.scrpy_maxsize.get().strip() or "0"
        a=["-s",self._device_serial,"--stay-awake","--no-audio","--video-bit-rate",br]
        if self.auto_screen_off.get():
            a.append("--turn-screen-off")
        if ms!="0": a.extend(["--max-size",ms])
        
        # 投屏完全独立: 不经过队列, 不占用is_running, 输出不显示
        self._log("[OK] 启动投屏中...", 'ok')
        try:
            p=subprocess.Popen([sp]+a, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            self.scrpcy_process=p
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
            self.scrpcy_process=None
            self._log("[OK] 投屏已关闭", 'ok')
        else: self._log("[!] 当前没有投屏进程",'warn')

    def _adb_key(self, c):
        """发送按键事件 - 独立执行, 不经过队列"""
        if not self._device_serial:
            self._log("[!] 未获取设备序列号，请先开始投屏", 'warn')
            return
        adb=get_tool_path('adb')
        try:
            subprocess.Popen([adb,"-s",self._device_serial,"shell","input","keyevent",str(c)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW)
            self._log(f"[OK] 按键: {c}", 'ok')
        except Exception as e:
            self._log(f"[ERR] 按键失败: {e}", 'err')

    def run(self):
        try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except: pass
        self.root.mainloop()

if __name__ == "__main__":
    App().run()