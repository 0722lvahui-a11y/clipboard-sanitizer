#!/usr/bin/env python3
"""
赵赵牌act神器 — Windows 版
==============================
- 复制含 act_ 的账号 → 去前缀 → 排队
- 每次 Ctrl+V 自动贴出下一个
- Win32 原生剪贴板 + 全局键盘钩子
"""

import tkinter as tk
import sys, os, time, threading, re, ctypes
from ctypes import wintypes
from collections import deque

IS_WIN = sys.platform == "win32"

# =========================== Win32 剪贴板 ===========================
CF_UNICODETEXT = 13

def read_clip():
    try:
        ctypes.windll.user32.OpenClipboard(0)
        h = ctypes.windll.user32.GetClipboardData(CF_UNICODETEXT)
        if h:
            lp = ctypes.windll.kernel32.GlobalLock(h)
            if lp:
                text = ctypes.c_wchar_p(lp).value
                ctypes.windll.kernel32.GlobalUnlock(lp)
                ctypes.windll.user32.CloseClipboard()
                return text or ""
        ctypes.windll.user32.CloseClipboard()
    except: pass
    return ""

def write_clip(text):
    try:
        ctypes.windll.user32.OpenClipboard(0)
        ctypes.windll.user32.EmptyClipboard()
        size = (len(text) + 1) * 2
        h = ctypes.windll.kernel32.GlobalAlloc(0x0002, size)
        lp = ctypes.windll.kernel32.GlobalLock(h)
        ctypes.cdll.msvcrt.wcscpy(ctypes.c_wchar_p(lp), text)
        ctypes.windll.kernel32.GlobalUnlock(h)
        ctypes.windll.user32.SetClipboardData(CF_UNICODETEXT, h)
        ctypes.windll.user32.CloseClipboard()
        return True
    except: return False

# =========================== 配色 ===========================
BG_PINK        = "#FFD6E0"
BG_PINK_DARK   = "#F4B8C8"
HEART_ON       = "#4CAF50"
HEART_ON_HOVER = "#66BB6A"
HEART_OFF      = "#BDBDBD"
HEART_OFF_HOVER = "#9E9E9E"
TEXT_DARK      = "#5D4037"
TEXT_HINT      = "#C4909A"
DECO_LINE      = "#F0B8C8"
LABEL_BG       = "#FFE4EC"
W = 320; H = 330

FONT_TITLE  = ("Microsoft YaHei", 13, "bold")
FONT_STATUS = ("Microsoft YaHei", 10)
FONT_HINT   = ("Microsoft YaHei", 9)
FONT_HEART  = ("Segoe UI Emoji", 48)

# =========================== 主应用 ===========================
class App:
    def __init__(self):
        self.enabled = True
        self.last_content = ""
        self.is_writing = False
        self.running = True
        self.queue = deque()
        self.queue_current = ""

        self.root = tk.Tk()
        self.root.title("赵赵牌act神器")
        self.root.geometry(f"{W}x{H}")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_PINK)
        # 置顶
        self.root.attributes("-topmost", True)

        try: self.root.iconbitmap(default="")
        except: pass

        self._build_ui()
        self.last_content = read_clip()
        self.root.after(300, self._poll_clipboard)
        self._start_key_listener()
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    # ==================== UI ====================
    def _build_ui(self):
        self.canvas = tk.Canvas(self.root, width=W, height=H,
                                highlightthickness=0, bd=0, bg=BG_PINK)
        self.canvas.pack(fill="both", expand=True)

        self.canvas.create_rectangle(0, 0, W, 4, fill=DECO_LINE, outline="")

        # 标题
        self.canvas.create_rectangle(30, 22, W - 30, 46, fill=LABEL_BG, outline="")
        self.canvas.create_text(W // 2, 34, text="✨  公主专用  ✨",
                                fill=TEXT_DARK, font=FONT_TITLE)

        # 爱心
        self.heart = self.canvas.create_text(W // 2, 105, text="❤️",
                                              fill=HEART_ON, font=FONT_HEART)
        self.canvas.tag_bind(self.heart, "<Button-1>", lambda e: self._toggle())
        self.canvas.tag_bind(self.heart, "<Enter>", self._heart_enter)
        self.canvas.tag_bind(self.heart, "<Leave>", self._heart_leave)
        self.canvas.tag_bind(self.heart, "<Enter>",
            lambda e: self.canvas.configure(cursor="hand2"), add="+")
        self.canvas.tag_bind(self.heart, "<Leave>",
            lambda e: self.canvas.configure(cursor=""), add="+")

        # 状态
        self.status = self.canvas.create_text(W // 2, 170,
            text="🟢  开启中 — 自动去除 act_", fill=TEXT_DARK, font=FONT_STATUS)

        # 队列
        self.queue_label = self.canvas.create_text(W // 2, 198, text="",
                                                    fill=TEXT_HINT, font=FONT_HINT)

        # 提示
        self.canvas.create_text(W // 2, 225,
            text="复制含 act_ 的内容 → Ctrl+V 逐个粘贴",
            fill=TEXT_HINT, font=FONT_HINT)

        # 按键反馈闪点
        self.ping_dot = self.canvas.create_oval(W//2-4, 248, W//2+4, 256,
                                                 fill="", outline="")

        # 底部
        self.canvas.create_rectangle(0, H - 3, W, H, fill=DECO_LINE, outline="")
        self.canvas.create_text(W // 2, H - 12, text="赵赵牌act神器  |  Windows",
                                 fill=TEXT_HINT, font=("Arial", 7))

    def _heart_enter(self, e):
        c = HEART_ON_HOVER if self.enabled else HEART_OFF_HOVER
        self.canvas.itemconfig(self.heart, fill=c)
    def _heart_leave(self, e):
        c = HEART_ON if self.enabled else HEART_OFF
        self.canvas.itemconfig(self.heart, fill=c)

    def _toggle(self):
        self.enabled = not self.enabled
        if self.enabled:
            self.canvas.itemconfig(self.heart, fill=HEART_ON)
            self.canvas.itemconfig(self.status, text="🟢  开启中 — 自动去除 act_")
        else:
            self.canvas.itemconfig(self.heart, fill=HEART_OFF)
            self.canvas.itemconfig(self.status, text="⚪  已暂停")
            self.queue.clear()
            self._update_queue_label()
        self._click_anim()

    def _click_anim(self):
        orig = FONT_HEART[1]
        self.canvas.itemconfig(self.heart, font=(FONT_HEART[0], orig + 8))
        self.root.after(60, lambda: self.canvas.itemconfig(self.heart, font=FONT_HEART))

    def _update_queue_label(self):
        n = len(self.queue)
        if n > 0:
            cur = self.queue_current or "?"
            self.canvas.itemconfig(self.queue_label,
                text=f"排队中: {n} 个  |  当前: {cur}")
        else:
            self.canvas.itemconfig(self.queue_label, text="")

    def _show_ping(self):
        """闪一下绿点表示检测到粘贴"""
        self.canvas.itemconfig(self.ping_dot, fill="#4CAF50")
        self.root.after(200, lambda: self.canvas.itemconfig(self.ping_dot, fill=""))

    # ==================== 键盘监听 ====================
    def _start_key_listener(self):
        try:
            from pynput.keyboard import Key, KeyCode, Listener
        except ImportError:
            self.canvas.itemconfig(self.status, text="⚠️  需安装 pynput")
            return

        def on_press(key):
            if not self.enabled: return
            try: is_ctrl = (key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r))
            except: is_ctrl = False
            try: is_v = (key == KeyCode.from_char('v') or key == KeyCode.from_char('V'))
            except: is_v = False

            if is_ctrl:
                self._ctrl_held = True
            if is_v and getattr(self, '_ctrl_held', False):
                # 标记粘贴并稍后切换
                self._paste_fired = True

        def on_release(key):
            try:
                if key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r):
                    self._ctrl_held = False
                    if getattr(self, '_paste_fired', False):
                        self._paste_fired = False
                        # 在 release 时切换——此时系统粘贴已完成
                        self.root.after(50, self._advance_queue)
            except: pass

        self._ctrl_held = False
        self._paste_fired = False
        t = threading.Thread(target=lambda: Listener(
            on_press=on_press, on_release=on_release).run(), daemon=True)
        t.start()

    # ==================== 队列 ====================
    def _advance_queue(self):
        if not self.enabled or not self.queue:
            return
        self.queue.popleft()  # 当前项已粘贴完，出队
        if self.queue:
            nxt = self.queue[0]
            self.queue_current = nxt
            self.is_writing = True
            write_clip(nxt)
            self.is_writing = False
            self.last_content = nxt
            self._update_queue_label()
            self._show_ping()
        else:
            self.queue_current = ""
            self._update_queue_label()

    def _process_act_content(self, content):
        cleaned = re.sub(r'act_', '', content)
        lines = re.split(r'[\n\r]+|\s{2,}', cleaned)
        numbers = [l.strip() for l in lines if l.strip()]
        if not numbers: return False

        self.queue.clear()
        for n in numbers: self.queue.append(n)

        first = self.queue[0]
        self.queue_current = first
        self.is_writing = True
        write_clip(first)
        self.is_writing = False
        self.last_content = first

        self._update_queue_label()
        return True

    # ==================== 轮询 ====================
    def _poll_clipboard(self):
        if not self.running: return
        if self.enabled and not self.is_writing:
            c = read_clip()
            if c and c != self.last_content:
                self.last_content = c
                if "act_" in c:
                    ok = self._process_act_content(c)
                    if ok:
                        self.canvas.itemconfig(self.status,
                            text=f"🟢  已处理 {len(self.queue)} 个账号")
        self.root.after(300, self._poll_clipboard)

    def _close(self):
        self.running = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    App().run()
