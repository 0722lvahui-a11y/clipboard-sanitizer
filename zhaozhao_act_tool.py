#!/usr/bin/env python3
"""
赵赵牌act神器 — Windows 版
==============================
- 复制含 act_ 的账号 → 去前缀 → 排队
- 自动每隔 2 秒切换剪贴板到下一个数字
- 你只管反复 Ctrl+V 就行
- 无需管理员权限，无需安装任何东西
"""

import tkinter as tk
import sys, os, re, ctypes, threading, time
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
W = 320; H = 360

FONT_TITLE  = ("Microsoft YaHei", 13, "bold")
FONT_STATUS = ("Microsoft YaHei", 10)
FONT_HINT   = ("Microsoft YaHei", 9)
FONT_HEART  = ("Segoe UI Emoji", 44)
FONT_TIMER  = ("Segoe UI Emoji", 14)

# =========================== 主应用 ===========================
class App:
    def __init__(self):
        self.enabled = True
        self.last_content = ""
        self.is_writing = False
        self.running = True
        self.queue = deque()
        self.queue_current = ""
        self.timer_count = 0  # 倒计时秒数
        self.pace = 2         # 切换间隔（秒）

        self.root = tk.Tk()
        self.root.title("赵赵牌act神器")
        self.root.geometry(f"{W}x{H}")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_PINK)
        self.root.attributes("-topmost", True)

        try: self.root.iconbitmap(default="")
        except: pass

        self._build_ui()
        self.last_content = read_clip()
        self.root.after(200, self._poll_clipboard)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    # ==================== UI ====================
    def _build_ui(self):
        self.canvas = tk.Canvas(self.root, width=W, height=H,
                                highlightthickness=0, bd=0, bg=BG_PINK)
        self.canvas.pack(fill="both", expand=True)

        self.canvas.create_rectangle(0, 0, W, 4, fill=DECO_LINE, outline="")

        # 标题
        self.canvas.create_rectangle(30, 22, W - 30, 46, fill=LABEL_BG, outline="")
        self.canvas.create_text(W // 2, 34, text="✨  朋友限定  ✨",
                                fill=TEXT_DARK, font=FONT_TITLE)

        # 爱心
        self.heart = self.canvas.create_text(W // 2, 100, text="❤️",
                                              fill=HEART_ON, font=FONT_HEART)
        self.canvas.tag_bind(self.heart, "<Button-1>", lambda e: self._toggle())
        self.canvas.tag_bind(self.heart, "<Enter>", self._heart_enter)
        self.canvas.tag_bind(self.heart, "<Leave>", self._heart_leave)
        self.canvas.tag_bind(self.heart, "<Enter>",
            lambda e: self.canvas.configure(cursor="hand2"), add="+")
        self.canvas.tag_bind(self.heart, "<Leave>",
            lambda e: self.canvas.configure(cursor=""), add="+")

        # 状态
        self.status = self.canvas.create_text(W // 2, 158,
            text="🟢  开启中 — 自动去除 act_", fill=TEXT_DARK, font=FONT_STATUS)

        # 倒计时圆环 + 文字
        self.timer_circle = self.canvas.create_oval(W//2-22, 178, W//2+22, 222,
                                                     outline=PINK_DARK, width=2)
        self.timer_text = self.canvas.create_text(W // 2, 200,
            text="--", fill=PINK_DARK, font=FONT_TIMER)

        # 队列
        self.queue_label = self.canvas.create_text(W // 2, 238, text="",
                                                    fill=TEXT_HINT, font=FONT_HINT)

        # 提示
        self.canvas.create_text(W // 2, 265,
            text="复制含 act_ → 自动排队 → 反复 Ctrl+V",
            fill=TEXT_HINT, font=FONT_HINT)

        self.hint_text = self.canvas.create_text(W // 2, 282,
            text=f"每 {self.pace} 秒自动切换下一个",
            fill=TEXT_HINT, font=("Microsoft YaHei", 8))

        # 加减速度按钮
        btn_y = 302
        self.pace_slow = self.canvas.create_text(W//2 - 60, btn_y, text="− 慢",
            fill=TEXT_HINT, font=("Microsoft YaHei", 10, "bold"))
        self.pace_val  = self.canvas.create_text(W//2, btn_y, text=f"{self.pace}s",
            fill=TEXT_DARK, font=("Microsoft YaHei", 10, "bold"))
        self.pace_fast = self.canvas.create_text(W//2 + 60, btn_y, text="快 ＋",
            fill=TEXT_HINT, font=("Microsoft YaHei", 10, "bold"))
        self.canvas.tag_bind(self.pace_slow, "<Button-1>", lambda e: self._change_pace(-1))
        self.canvas.tag_bind(self.pace_fast, "<Button-1>", lambda e: self._change_pace(+1))
        self.canvas.tag_bind(self.pace_slow, "<Enter>",
            lambda e: self.canvas.itemconfig(self.pace_slow, fill=PINK_DARK))
        self.canvas.tag_bind(self.pace_slow, "<Leave>",
            lambda e: self.canvas.itemconfig(self.pace_slow, fill=TEXT_HINT))
        self.canvas.tag_bind(self.pace_fast, "<Enter>",
            lambda e: self.canvas.itemconfig(self.pace_fast, fill=PINK_DARK))
        self.canvas.tag_bind(self.pace_fast, "<Leave>",
            lambda e: self.canvas.itemconfig(self.pace_fast, fill=TEXT_HINT))

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
            self._update_queue()
            self.canvas.itemconfig(self.timer_text, text="--")
        self._click_anim()

    def _click_anim(self):
        orig = FONT_HEART[1]
        self.canvas.itemconfig(self.heart, font=(FONT_HEART[0], orig + 8))
        self.root.after(60, lambda: self.canvas.itemconfig(self.heart, font=FONT_HEART))

    def _update_queue(self):
        n = len(self.queue)
        if n > 0:
            cur = self.queue_current or "?"
            self.canvas.itemconfig(self.queue_label,
                text=f"排队: {n} 个  |  当前: {cur}")
        else:
            self.canvas.itemconfig(self.queue_label, text="")

    def _update_timer(self, sec):
        self.canvas.itemconfig(self.timer_text, text=str(sec))
        # 圆环颜色：越接近0越深
        ratio = sec / max(self.pace, 1)
        if ratio < 0.3: clr = "#D4919E"
        elif ratio < 0.6: clr = "#E0A0B0"
        else: clr = PINK_DARK
        self.canvas.itemconfig(self.timer_circle, outline=clr)

    def _change_pace(self, delta):
        self.pace = max(1, min(5, self.pace + delta))
        self.canvas.itemconfig(self.pace_val, text=f"{self.pace}s")
        self.canvas.itemconfig(self.hint_text, text=f"每 {self.pace} 秒自动切换下一个")

    # ==================== 定时切换 ====================
    def _start_timer(self):
        """启动倒计时，到0时切换剪贴板"""
        if not self.enabled or not self.queue:
            return
        if len(self.queue) <= 1 and self.queue_current == (self.queue[0] if self.queue else ""):
            # 只剩最后一个了，不需要再切换
            self.canvas.itemconfig(self.timer_text, text="✓")
            self.canvas.itemconfig(self.timer_circle, outline=HEART_ON)
            return

        self.timer_count = self.pace
        self._update_timer(self.timer_count)
        self._tick()

    def _tick(self):
        if not self.enabled or not self.queue or len(self.queue) <= 1:
            return
        self.timer_count -= 1
        if self.timer_count <= 0:
            # 切换
            self._advance_queue()
            if len(self.queue) > 1:
                self.timer_count = self.pace
                self._update_timer(self.timer_count)
                self.root.after(1000, self._tick)
            else:
                self.canvas.itemconfig(self.timer_text, text="✓")
                self.canvas.itemconfig(self.timer_circle, outline=HEART_ON)
        else:
            self._update_timer(self.timer_count)
            self.root.after(1000, self._tick)

    def _advance_queue(self):
        if not self.queue: return
        self.queue.popleft()
        if self.queue:
            nxt = self.queue[0]
            self.queue_current = nxt
            self.is_writing = True
            write_clip(nxt)
            self.is_writing = False
            self.last_content = nxt
            self._update_queue()

    # ==================== 处理 ====================
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

        self._update_queue()
        self.canvas.itemconfig(self.status,
            text=f"🟢  已加载 {len(self.queue)} 个 | 快按 Ctrl+V")

        # 启动倒计时
        self._start_timer()
        return True

    # ==================== 轮询 ====================
    def _poll_clipboard(self):
        if not self.running: return
        if self.enabled and not self.is_writing:
            c = read_clip()
            if c and c != self.last_content:
                self.last_content = c
                if "act_" in c:
                    self._process_act_content(c)
        self.root.after(200, self._poll_clipboard)

    def _close(self):
        self.running = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    App().run()
