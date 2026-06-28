#!/usr/bin/env python3
"""
工单 act_ 查询工具（Mac 桌面版）
- 粘贴工单编号 → 点击开始 → 逐个自动查询 → 结果复制
- 可见浏览器操作，不会被误判为后台恶意程序
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os, re, time, threading, subprocess, queue

IS_MAC = sys.platform == "darwin"

# =========================== 配色 ===========================
BG_MAIN  = "#F5F0F5"
BG_CARD  = "#FFFFFF"
PINK     = "#E8B4B8"
PINK_D   = "#D4919E"
TEXT     = "#4A3040"
HINT     = "#B8A0A8"
GREEN    = "#5B8C5A"
RED      = "#C45C5C"

FONT_TITLE  = ("PingFang SC" if IS_MAC else "Microsoft YaHei", 14, "bold")
FONT_LABEL  = ("PingFang SC" if IS_MAC else "Microsoft YaHei", 11)
FONT_RESULT = ("Menlo" if IS_MAC else "Consolas", 10)

W = 680; H = 560
URL = "https://mediahub.meetsocial.cn/account/workOrder?_workOrderStatusList%5B0%5D=102"

# =========================== Chrome 查找 ===========================
def find_chrome():
    paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ]
    for p in paths:
        if os.path.isfile(p): return p
    return None

# =========================== 主界面 ===========================
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("工单 act_ 查询")
        self.root.geometry(f"{W}x{H}")
        self.root.configure(bg=BG_MAIN)
        self._running = False

        # ---- 标题 ----
        tk.Label(self.root, text="📋  工单 act_ 账户查询", font=FONT_TITLE,
                 fg=TEXT, bg=BG_MAIN).pack(pady=(16,4))
        tk.Label(self.root, text="粘贴工单编号，一行一个，点击开始自动查询",
                 font=(FONT_LABEL[0], 9), fg=HINT, bg=BG_MAIN).pack()

        # ---- 输入卡片 ----
        card = tk.Frame(self.root, bg=BG_CARD, highlightthickness=1,
                        highlightbackground="#E8D8DC")
        card.pack(fill="both", expand=True, padx=20, pady=(10,6))

        tk.Label(card, text="工单编号（一行一个）:", font=FONT_LABEL,
                 fg=TEXT, bg=BG_CARD).pack(pady=(12,4), anchor="w", padx=14)

        self.input_text = tk.Text(card, font=FONT_RESULT, height=8,
                                   relief="solid", borderwidth=1,
                                   wrap="none")
        self.input_text.pack(fill="both", expand=True, padx=14, pady=(0,8))

        # 示例
        self.input_text.insert("1.0", "# 在此粘贴工单编号，一行一个，像这样：\n"
                              "# WD32026061909135121387667517\n"
                              "# WD32026061818575170767591018\n")

        # ---- 按钮 ----
        btn_row = tk.Frame(self.root, bg=BG_MAIN)
        btn_row.pack(pady=4)

        self.start_btn = tk.Button(btn_row, text="▶  开始查询", font=FONT_LABEL,
                                    bg=PINK, fg="white", activebackground=PINK_D,
                                    relief="flat", padx=24, pady=4, cursor="hand2",
                                    command=self._start)
        self.start_btn.pack(side="left", padx=4)

        self.stop_btn = tk.Button(btn_row, text="⏹ 停止", font=FONT_LABEL,
                                   bg="#C0C0C0", fg="white", relief="flat",
                                   padx=24, pady=4, cursor="hand2",
                                   command=self._stop, state="disabled")
        self.stop_btn.pack(side="left", padx=4)

        # ---- 进度 ----
        self.status_var = tk.StringVar(value="就绪 — 粘贴工单编号后点击「开始查询」")
        tk.Label(self.root, textvariable=self.status_var, font=(FONT_LABEL[0], 9),
                 fg=HINT, bg=BG_MAIN).pack(pady=2)
        self.progress = ttk.Progressbar(self.root, mode="determinate")
        self.progress.pack(fill="x", padx=20, pady=2)

        # ---- 结果 ----
        result_card = tk.Frame(self.root, bg=BG_CARD, highlightthickness=1,
                               highlightbackground="#E8D8DC")
        result_card.pack(fill="both", expand=True, padx=20, pady=(4,8))

        self.result_text = tk.Text(result_card, font=FONT_RESULT, height=6,
                                    relief="solid", borderwidth=1)
        self.result_text.pack(fill="both", expand=True, padx=14, pady=(12,4))

        # 复制按钮
        self.copy_btn = tk.Button(result_card, text="📋  一键复制结果", font=FONT_LABEL,
                                   bg="#D4C5A9", fg="white", relief="flat",
                                   padx=16, pady=3, cursor="hand2",
                                   command=self._copy)
        self.copy_btn.pack(pady=(0,10))

        self.result_queue = queue.Queue()
        self._poll_queue()
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    # ==================== 逻辑 ====================
    def _start(self):
        if self._running: return
        raw = self.input_text.get("1.0", "end")
        orders = []
        for line in raw.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("//"):
                orders.append(line)

        if not orders:
            messagebox.showwarning("提示", "请粘贴至少一个工单编号")
            return

        chrome = find_chrome()
        if not chrome:
            messagebox.showerror("错误", "未找到 Chrome 浏览器\n请安装 Google Chrome")
            return

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            messagebox.showerror("缺少依赖",
                "请先运行: pip install playwright\n然后: playwright install chromium")
            return

        self.orders = orders
        self._running = True
        self.start_btn.config(state="disabled", bg="#C0C0C0")
        self.stop_btn.config(state="normal", bg="#E07070")
        self.progress["maximum"] = len(orders)
        self.progress["value"] = 0
        self.result_text.delete("1.0", "end")
        self.results = []

        t = threading.Thread(target=self._run, args=(orders, chrome, sync_playwright),
                             daemon=True)
        t.start()

    def _stop(self):
        self._running = False
        self._queue(("status", "正在停止..."))
        self.stop_btn.config(state="disabled")

    def _run(self, orders, chrome_path, sp):
        try:
            p = sp()
            browser = p.chromium.launch(headless=False, executable_path=chrome_path)
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            page.set_default_timeout(15000)

            page.goto(URL, timeout=25000)
            page.wait_for_timeout(3000)

            if "login" in page.url.lower():
                self._queue(("status", "⚠️  请手动登录，30秒后自动继续..."))
                time.sleep(30)

            total = len(orders)
            for i, oid in enumerate(orders):
                if not self._running: break
                self._queue(("status", f"查询中: {i+1}/{total}  {oid}"))
                self._queue(("progress", i+1))

                try:
                    page.goto(URL, timeout=15000)
                    page.wait_for_timeout(1500)

                    # 找搜索框 & 输入
                    search = None
                    for s in ['input[placeholder*="工单"]','input[placeholder*="编号"]',
                              'input[placeholder*="搜索"]','input[name*="order"]',
                              'input[name*="workOrder"]','.el-input__inner']:
                        try:
                            if page.locator(s).first.count() > 0:
                                search = page.locator(s).first; break
                        except: pass

                    if search:
                        search.click(); search.fill(""); search.type(oid, delay=40)
                    else:
                        page.keyboard.press("Control+a")
                        page.keyboard.type(oid, delay=40)

                    page.keyboard.press("Enter")
                    page.wait_for_timeout(2500)

                    # 点进详情
                    clicked = False
                    for s in [f'text={oid}', f'a:has-text("{oid}")',
                              f'[class*="link"]:has-text("{oid}")']:
                        try:
                            if page.locator(s).first.count() > 0:
                                page.locator(s).first.click(); clicked = True; break
                        except: pass

                    if not clicked:
                        self.results.append((oid, "未找到", ""))
                        self._queue(("result", f"{oid}\t未找到\n"))
                        continue

                    page.wait_for_timeout(3000)

                    acts = re.findall(r'act_[a-zA-Z0-9_]+', page.inner_text("body"))
                    uniq = list(set(acts))
                    cnt = len(uniq)
                    acts_str = ", ".join(sorted(uniq))
                    self.results.append((oid, str(cnt), acts_str))
                    self._queue(("result", f"{oid}\t{cnt}\t{acts_str}\n"))
                    time.sleep(0.3)

                except Exception as e:
                    self.results.append((oid, "出错", str(e)[:80]))
                    self._queue(("result", f"{oid}\t出错\t{str(e)[:80]}\n"))

            browser.close(); p.stop()
            self._queue(("done", None))
            self._queue(("status", f"完成！共查询 {len(self.results)} 个工单"))
        except Exception as e:
            self._queue(("status", f"异常: {e}"))
            self._queue(("done", None))

    def _queue(self, msg):
        self.result_queue.put(msg)

    def _poll_queue(self):
        try:
            while True:
                typ, val = self.result_queue.get_nowait()
                if typ == "status": self.status_var.set(val)
                elif typ == "progress": self.progress["value"] = val
                elif typ == "result":
                    self.result_text.insert("end", val)
                    self.result_text.see("end")
                elif typ == "done":
                    self._running = False
                    self.start_btn.config(state="normal", bg=PINK)
                    self.stop_btn.config(state="disabled", bg="#C0C0C0")
        except queue.Empty: pass
        self.root.after(100, self._poll_queue)

    def _copy(self):
        text = "工单编号\tact_账户数\t账户列表\n"
        for oid, cnt, acts in self.results:
            text += f"{oid}\t{cnt}\t{acts}\n"
        if IS_MAC:
            subprocess.run(["pbcopy"], input=text, text=True)
        else:
            self.root.clipboard_clear(); self.root.clipboard_append(text)
        messagebox.showinfo("已复制", f"已复制 {len(self.results)} 条结果")

    def _close(self):
        self._running = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    App().run()
