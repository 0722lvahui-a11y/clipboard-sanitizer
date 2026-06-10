#!/usr/bin/env python3
"""
黑毛猪净化器 — 自动去除 act_ 前缀
===================================
- 监测剪贴板内容，检测到「act_」字段后自动去除
- 只保留 act_ 之后的内容
- 少女粉主题 UI，爱心按钮开关
- 支持自定义背景图 (background.png)
- 跨平台支持 macOS / Windows / Linux

纯 Python 实现，无需安装任何第三方库。
运行方式：python clipboard_sanitizer.py
"""

import tkinter as tk
import sys
import os
import subprocess
import platform

# =========================== 平台检测 ===========================

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

# =========================== 资源路径 ===========================

def resource_path(relative):
    """获取资源文件路径，兼容 PyInstaller 打包"""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative)

# =========================== 配色方案 (少女粉主题) ===========================

BG_PINK        = "#FFD6E0"   # 主背景 — 少女粉
BG_PINK_DARK   = "#F4B8C8"   # 深粉 (装饰条 / 悬停)
HEART_ON       = "#4CAF50"   # 爱心开启 — 绿色
HEART_ON_HOVER = "#66BB6A"   # 爱心开启悬停 — 亮绿
HEART_OFF      = "#BDBDBD"   # 爱心关闭 — 灰色
HEART_OFF_HOVER = "#9E9E9E"  # 爱心关闭悬停 — 深灰
TEXT_DARK      = "#5D4037"   # 深棕文字
TEXT_HINT      = "#C4909A"   # 提示文字
DECO_LINE      = "#F0B8C8"   # 装饰线颜色

# ---- 文字底色（半透明效果通过颜色模拟）----
LABEL_BG       = "#FFE4EC"   # 标签底衬 — 比背景稍深一点点

# =========================== 字体 (跨平台适配) ===========================

if IS_MAC:
    FONT_TITLE   = ("PingFang SC", 13, "bold")
    FONT_STATUS  = ("PingFang SC", 10)
    FONT_HINT    = ("PingFang SC", 9)
    FONT_HEART   = ("Apple Color Emoji", 56)
else:
    FONT_TITLE   = ("Microsoft YaHei", 12, "bold")
    FONT_STATUS  = ("Microsoft YaHei", 10)
    FONT_HINT    = ("Microsoft YaHei", 9)
    FONT_HEART   = ("Segoe UI Emoji", 52)

# =========================== 常量 ===========================

WINDOW_WIDTH   = 320
WINDOW_HEIGHT  = 300
POLL_INTERVAL  = 400   # 剪贴板轮询间隔 (毫秒)
ACT_MARKER     = "act_"


# =========================== 主应用 ===========================

class ClipboardSanitizer:
    """黑毛猪净化器 — 自动去除 act_ 前缀"""

    def __init__(self):
        # ---- 状态 ----
        self.enabled         = True
        self.last_content    = ""
        self.is_modifying    = False
        self.running         = True
        self.bg_image        = None

        # ---- 窗口 ----
        self.root = tk.Tk()
        self.root.title("黑毛猪净化器 NEW")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)

        # 窗口图标
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

        # ---- 画布（承载背景图 + 所有控件） ----
        self.canvas = tk.Canvas(
            self.root,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # ---- 构建 UI ----
        self._build_ui()

        # ---- 初始化剪贴板追踪 ----
        self.last_content = self._read_clipboard()

        # ---- 启动剪贴板轮询 ----
        self.root.after(POLL_INTERVAL, self._poll)

        # ---- 关闭处理 ----
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Command-q>" if IS_MAC else "<Control-q>", lambda e: self._on_close())

    # ==================== UI 构建 ====================

    def _build_ui(self):
        """构建全部界面组件"""

        # ==== 背景图片 ====
        bg_loaded = False
        for fname in ("background.png", "background.gif"):
            path = resource_path(fname)
            if os.path.exists(path):
                try:
                    img = tk.PhotoImage(file=path)
                    # 缩放图片以适应窗口
                    if img.width() != WINDOW_WIDTH or img.height() != WINDOW_HEIGHT:
                        img = img.zoom(1, 1)  # 保持原样，不做缩放
                    self.bg_image = img
                    self.canvas.create_image(0, 0, image=self.bg_image, anchor="nw")
                    bg_loaded = True
                    break
                except Exception:
                    continue

        if not bg_loaded:
            self.canvas.configure(bg=BG_PINK)

        # ==== 顶部透明条 ====
        self.canvas.create_rectangle(
            0, 0, WINDOW_WIDTH, 4,
            fill=DECO_LINE, outline="",
        )

        # ==== 标题 - 添加底衬使其在图片上可读 ====
        title_frame = self.canvas.create_rectangle(
            30, 22, WINDOW_WIDTH - 30, 46,
            fill=LABEL_BG, outline="", stipple="" if not bg_loaded else "gray25",
        )
        title_id = self.canvas.create_text(
            WINDOW_WIDTH // 2, 34,
            text="✨  公主专用  ✨",
            fill=TEXT_DARK,
            font=FONT_TITLE,
        )

        # 如果没背景图，去掉底衬矩形
        if not bg_loaded:
            self.canvas.delete(title_frame)

        # ==== 爱心按钮 ====
        self.heart_id = self.canvas.create_text(
            WINDOW_WIDTH // 2, 110,
            text="❤️",
            fill=HEART_ON,
            font=FONT_HEART,
        )
        self.canvas.tag_bind(self.heart_id, "<Button-1>", lambda e: self._toggle())
        self.canvas.tag_bind(self.heart_id, "<Enter>", self._on_heart_enter)
        self.canvas.tag_bind(self.heart_id, "<Leave>", self._on_heart_leave)

        # 爱心 — 手指光标
        self.canvas.tag_bind(self.heart_id, "<Enter>",
            lambda e: self.canvas.configure(cursor="hand2"), add="+")
        self.canvas.tag_bind(self.heart_id, "<Leave>",
            lambda e: self.canvas.configure(cursor=""), add="+")

        # ==== 状态文字 ====
        status_y = 175
        if not bg_loaded:
            status_frame = 0  # no bg means no frame needed
        else:
            status_frame = self.canvas.create_rectangle(
                40, status_y - 10, WINDOW_WIDTH - 40, status_y + 10,
                fill=LABEL_BG, outline="",
            )

        self.status_id = self.canvas.create_text(
            WINDOW_WIDTH // 2, status_y,
            text="🟢  净化中 — 自动去除 act_",
            fill=TEXT_DARK,
            font=FONT_STATUS,
        )

        # ==== 提示文字 ====
        hint_y = 200
        self.canvas.create_text(
            WINDOW_WIDTH // 2, hint_y,
            text="点击爱心开启 / 关闭净化",
            fill=TEXT_HINT,
            font=FONT_HINT,
        )

        # ==== 底部信息 ====
        self.canvas.create_rectangle(
            0, WINDOW_HEIGHT - 3, WINDOW_WIDTH, WINDOW_HEIGHT,
            fill=DECO_LINE, outline="",
        )
        self.canvas.create_text(
            WINDOW_WIDTH // 2, WINDOW_HEIGHT - 12,
            text="v2.0  |  macOS / Windows",
            fill=TEXT_HINT,
            font=("Arial", 7),
        )

    # ---- 爱心悬停效果 ----

    def _on_heart_enter(self, event):
        if self.enabled:
            self.canvas.itemconfig(self.heart_id, fill=HEART_ON_HOVER)
        else:
            self.canvas.itemconfig(self.heart_id, fill=HEART_OFF_HOVER)

    def _on_heart_leave(self, event):
        if self.enabled:
            self.canvas.itemconfig(self.heart_id, fill=HEART_ON)
        else:
            self.canvas.itemconfig(self.heart_id, fill=HEART_OFF)

    # ==================== 开关切换 ====================

    def _toggle(self):
        self.enabled = not self.enabled

        if self.enabled:
            self.canvas.itemconfig(self.heart_id, fill=HEART_ON)
            self.canvas.itemconfig(self.status_id,
                text="🟢  净化中 — 自动去除 act_")
        else:
            self.canvas.itemconfig(self.heart_id, fill=HEART_OFF)
            self.canvas.itemconfig(self.status_id,
                text="⚪  已暂停 — 点击爱心开启")

        self._click_animation()

    def _click_animation(self):
        original = FONT_HEART[1]
        self.canvas.itemconfig(self.heart_id, font=(FONT_HEART[0], original + 8))
        self.root.after(60, lambda: self.canvas.itemconfig(
            self.heart_id, font=FONT_HEART))

    # ==================== 跨平台剪贴板读写 ====================

    def _read_clipboard(self):
        """读取剪贴板 — macOS 用 pbpaste，其他用 tkinter"""
        if IS_MAC:
            try:
                r = subprocess.run(
                    ["pbpaste"], capture_output=True, text=True, timeout=2
                )
                return r.stdout.strip() if r.returncode == 0 else ""
            except Exception:
                return ""
        else:
            try:
                return self.root.clipboard_get().strip()
            except (tk.TclError, Exception):
                return ""

    def _write_clipboard(self, text):
        """写入剪贴板 — macOS 用 pbcopy，其他用 tkinter"""
        if IS_MAC:
            try:
                subprocess.run(
                    ["pbcopy"], input=text, text=True, timeout=2
                )
                return True
            except Exception:
                return False
        else:
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
                return True
            except Exception:
                return False

    # ==================== 剪贴板轮询 ====================

    def _poll(self):
        if not self.running:
            return

        if self.enabled and not self.is_modifying:
            content = self._read_clipboard()
            if content and content != self.last_content:
                self.last_content = content
                self._process_content(content)

        self.root.after(POLL_INTERVAL, self._poll)

    def _process_content(self, content: str):
        if ACT_MARKER not in content:
            return

        idx = content.find(ACT_MARKER)
        new_content = content[idx + len(ACT_MARKER):]

        if not new_content:
            print("[ClipSanitizer] ⚠️  act_ 之后无内容，跳过处理")
            return

        self.is_modifying = True
        ok = self._write_clipboard(new_content)
        if ok:
            self.last_content = new_content
            old_preview = content[:40] + "..." if len(content) > 40 else content
            new_preview = new_content[:40] + "..." if len(new_content) > 40 else new_content
            print(f"[ClipSanitizer] ✅ 已处理 act_")
            print(f"  处理前: {old_preview}")
            print(f"  处理后: {new_preview}")
        else:
            print("[ClipSanitizer] ❌ 写入剪贴板失败")
        self.is_modifying = False

    # ==================== 生命周期 ====================

    def _on_close(self):
        self.running = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# =========================== 入口 ===========================

def main():
    app = ClipboardSanitizer()
    app.run()


if __name__ == "__main__":
    main()
