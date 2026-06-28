#!/usr/bin/env python3
"""
剪贴板历史 — Mac 桌面版
- 自动记录剪贴板内容 + 复制时间
- 时间倒序排列
- 点击即可复制（不重复入历史）
- 已复制 → 灰色 / 未复制 → 粉色
- 少女粉主题
"""

import tkinter as tk
from tkinter import ttk
import sys, os, subprocess, threading, time
from datetime import datetime

IS_MAC = sys.platform == "darwin"

# =========================== 配色（沿用公主净化器风格）===========================
BG_MAIN   = "#FFD6E0"
BG_CARD   = "#FFFFFF"
PINK      = "#FFD6E0"
PINK_DARK = "#F4B8C8"
GRAY      = "#ECECEC"
GRAY_DARK = "#D8D8D8"
TEXT_DARK  = "#5D4037"
TEXT_HINT  = "#C4909A"

FONT_ITEM   = ("PingFang SC", 11)
FONT_TIME   = ("PingFang SC", 8)
FONT_TITLE  = ("PingFang SC", 14, "bold")

W = 420; H = 540

# =========================== 跨平台剪贴板 ===========================
def read_clipboard():
    try:
        r = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=1)
        return r.stdout if r.returncode == 0 else ""
    except: return ""

def write_clipboard(text):
    try:
        subprocess.run(["pbcopy"], input=text, text=True, timeout=1)
        return True
    except: return False

# =========================== 主应用 ===========================
class App:
    def __init__(self):
        self.history = []          # [{text, time, copied}, ...]  最新在前
        self.last_content = ""
        self.self_writing = False  # 防止自己写入时触发记录
        self.running = True

        # 窗口
        self.root = tk.Tk()
        self.root.title("剪贴板历史")
        self.root.geometry(f"{W}x{H}")
        self.root.minsize(340, 380)
        self.root.configure(bg=BG_MAIN)

        self._build_ui()

        self.last_content = read_clipboard()
        self.root.after(400, self._poll)

        self.root.protocol("WM_DELETE_WINDOW", self._close)

    # ==================== UI ====================
    def _build_ui(self):
        # 顶部装饰
        tk.Frame(self.root, bg=PINK_DARK, height=4).pack(fill="x")

        # 标题
        head = tk.Frame(self.root, bg=BG_MAIN)
        head.pack(pady=(16, 4))
        tk.Label(head, text="✨  公主专用  ✨", font=FONT_TITLE,
                 fg=TEXT_DARK, bg=BG_MAIN).pack()

        tk.Label(self.root, text="自动记录剪贴板 · 点击即可复制",
                 font=FONT_TIME, fg=TEXT_HINT, bg=BG_MAIN).pack(pady=(0, 10))

        # ---- 列表（Canvas 滚动）----
        outer = tk.Frame(self.root, bg=BG_MAIN)
        outer.pack(fill="both", expand=True, padx=14, pady=(0,8))

        self.canvas = tk.Canvas(outer, bg=BG_MAIN, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)

        self.items = tk.Frame(self.canvas, bg=BG_MAIN)
        self.items.bind("<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self._cwin = self.canvas.create_window((0,0), window=self.items,
                                                anchor="nw", tags="win")
        self.canvas.configure(yscrollcommand=scroll.set)

        # 滚轮
        def wheel(e):
            self.canvas.yview_scroll(-1 * (e.delta // 120), "units")
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self._cwin, width=e.width))

        self.canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # ---- 底部 ----
        bot = tk.Frame(self.root, bg=BG_MAIN)
        bot.pack(pady=(0, 12))

        self.clear_btn = tk.Button(bot, text="清空历史", font=("PingFang SC", 10),
                                    bg=GRAY, fg=TEXT_DARK, activebackground=GRAY_DARK,
                                    relief="flat", padx=18, pady=3, cursor="hand2",
                                    command=self._clear)
        self.clear_btn.pack(side="left", padx=4)

        self.count_lbl = tk.Label(bot, text="0 条记录", font=FONT_TIME,
                                  fg=TEXT_HINT, bg=BG_MAIN)
        self.count_lbl.pack(side="left", padx=(14,0))

        # 底部装饰
        tk.Frame(self.root, bg=PINK_DARK, height=3).pack(fill="x")

    # ==================== 轮询 ====================
    def _poll(self):
        if not self.running: return
        if not self.self_writing:
            c = read_clipboard()
            if c and c.strip() and c != self.last_content:
                self.last_content = c
                # 去重
                if not self.history or self.history[0]["text"] != c:
                    self.history.insert(0, {
                        "text": c,
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "copied": False,
                    })
                    self._draw()
        self.root.after(500, self._poll)

    # ==================== 渲染 ====================
    def _draw(self):
        for w in self.items.winfo_children():
            w.destroy()

        if not self.history:
            tk.Label(self.items, text="📌  还没有记录\n复制一段文字试试~",
                     font=FONT_ITEM, fg=TEXT_HINT, bg=BG_MAIN).pack(pady=50)
        else:
            for i, e in enumerate(self.history):
                self._card(e, i)

        self.count_lbl.config(text=f"{len(self.history)} 条记录")
        self.canvas.yview_moveto(0)

    def _card(self, entry, idx):
        copied = entry["copied"]
        bg = GRAY if copied else PINK
        border = GRAY_DARK if copied else PINK_DARK
        tc = "#BBBBBB" if copied else "#D4919E"
        txt_clr = "#999999" if copied else TEXT_DARK

        card = tk.Frame(self.items, bg=bg, highlightthickness=1,
                        highlightbackground=border, cursor="hand2")
        card.pack(fill="x", pady=2, ipady=2)

        # 点击事件
        def click(e, i=idx):
            self._on_copy(i)
        card.bind("<Button-1>", click)

        # 时间行
        tr = tk.Frame(card, bg=bg)
        tr.pack(fill="x", padx=12, pady=(8,2))
        tk.Label(tr, text=entry["time"], font=FONT_TIME,
                 fg=tc, bg=bg).pack(side="left")
        if copied:
            tk.Label(tr, text="✓ 已复制", font=FONT_TIME,
                     fg="#BBBBBB", bg=bg).pack(side="right")

        # 正文
        txt = entry["text"]
        disp = txt[:250] + ("..." if len(txt) > 250 else "")
        lbl = tk.Label(card, text=disp, font=FONT_ITEM, fg=txt_clr, bg=bg,
                       wraplength=W - 48, justify="left", anchor="w")
        lbl.pack(fill="x", padx=12, pady=(2,8))
        lbl.bind("<Button-1>", click)

    def _on_copy(self, idx):
        e = self.history[idx]
        self.self_writing = True
        ok = write_clipboard(e["text"])
        self.self_writing = False
        if ok:
            self.last_content = e["text"]
            e["copied"] = True
            self._draw()

    def _clear(self):
        self.history = []
        self._draw()

    def _close(self):
        self.running = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    App().run()
