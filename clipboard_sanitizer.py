#!/usr/bin/env python3
"""
剪贴板净化器 — 自动去除 act_ 前缀
===================================
- 监测剪贴板内容，检测到「act_」字段后自动去除
- 只保留 act_ 之后的内容
- 少女粉主题 UI，爱心按钮开关
- 开启：绿色爱心   关闭：灰色爱心
- 跨平台支持 macOS / Windows / Linux

纯 Python 实现，无需安装任何第三方库。
运行方式：python clipboard_sanitizer.py
"""

import tkinter as tk
import sys
import platform

# =========================== 平台检测 ===========================

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

# =========================== 配色方案 (少女粉主题) ===========================

BG_PINK        = "#FFD6E0"   # 主背景 — 少女粉
BG_PINK_LIGHT  = "#FFEBF0"   # 浅粉 (备用)
BG_PINK_DARK   = "#F4B8C8"   # 深粉 (装饰条 / 悬停)
HEART_ON       = "#4CAF50"   # 爱心开启 — 绿色
HEART_ON_HOVER = "#66BB6A"   # 爱心开启悬停 — 亮绿
HEART_OFF      = "#BDBDBD"   # 爱心关闭 — 灰色
HEART_OFF_HOVER = "#9E9E9E"  # 爱心关闭悬停 — 深灰
TEXT_DARK      = "#5D4037"   # 深棕文字
TEXT_LIGHT     = "#8D6E63"   # 浅棕文字
TEXT_HINT      = "#C4909A"   # 提示文字
DECO_LINE      = "#F0B8C8"   # 装饰线颜色

# =========================== 字体 (跨平台适配) ===========================

if IS_MAC:
    FONT_TITLE   = ("PingFang SC", 13, "bold")
    FONT_STATUS  = ("PingFang SC", 10)
    FONT_HINT    = ("PingFang SC", 9)
    FONT_HEART   = ("Apple Color Emoji", 56)
    MONO_FONT    = ("Menlo", 10)
else:
    FONT_TITLE   = ("Microsoft YaHei", 12, "bold")
    FONT_STATUS  = ("Microsoft YaHei", 10)
    FONT_HINT    = ("Microsoft YaHei", 9)
    FONT_HEART   = ("Segoe UI Emoji", 52)
    MONO_FONT    = ("Consolas", 10)

# =========================== 常量 ===========================

WINDOW_WIDTH   = 280
WINDOW_HEIGHT  = 260
POLL_INTERVAL  = 400   # 剪贴板轮询间隔 (毫秒)
ACT_MARKER     = "act_"


# =========================== 主应用 ===========================

class ClipboardSanitizer:
    """剪贴板净化器 — 自动去除 act_ 前缀"""

    def __init__(self):
        # ---- 状态 ----
        self.enabled         = True          # 净化开关
        self.last_content    = ""            # 上一次剪贴板内容 (去重用)
        self.is_modifying    = False         # 标记：正在由本程序修改剪贴板
        self.running         = True          # 运行标志

        # ---- 窗口 ----
        self.root = tk.Tk()
        self.root.title("Clip Sanitizer ❤️")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_PINK)

        # 窗口置顶
        self.root.attributes("-topmost", True)

        # 尝试设置窗口图标 (静默失败)
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

        # ---- 构建 UI ----
        self._build_ui()

        # ---- 初始化剪贴板追踪 ----
        try:
            self.last_content = self.root.clipboard_get().strip()
        except Exception:
            self.last_content = ""

        # ---- 启动剪贴板轮询 ----
        self.root.after(POLL_INTERVAL, self._poll)

        # ---- 关闭处理 ----
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # ---- 快捷键 ----
        self.root.bind("<Command-q>" if IS_MAC else "<Control-q>", lambda e: self._on_close())

        print(f"[ClipSanitizer] 启动完成 — 平台: {platform.system()}, 轮询间隔: {POLL_INTERVAL}ms")
        print(f"[ClipSanitizer] 当前状态: {'🟢 已开启' if self.enabled else '⚪ 已暂停'}")

    # ==================== UI 构建 ====================

    def _build_ui(self):
        """构建全部界面组件"""

        # ---- 顶部装饰条 ----
        deco_top = tk.Frame(self.root, bg=DECO_LINE, height=3)
        deco_top.pack(fill="x")

        # ---- 标题 ----
        self._title_label = tk.Label(
            self.root,
            text="✨  剪贴板净化器  ✨",
            bg=BG_PINK,
            fg=TEXT_DARK,
            font=FONT_TITLE,
        )
        self._title_label.pack(pady=(18, 6))

        # ---- 爱心按钮 (核心交互) ----
        self.heart_btn = tk.Label(
            self.root,
            text="❤️",
            bg=BG_PINK,
            fg=HEART_ON,
            font=FONT_HEART,
            cursor="hand2",
        )
        self.heart_btn.pack(pady=4)
        self.heart_btn.bind("<Button-1>", lambda e: self._toggle())
        self.heart_btn.bind("<Enter>", self._on_heart_enter)
        self.heart_btn.bind("<Leave>", self._on_heart_leave)

        # ---- 状态文字 ----
        self.status_label = tk.Label(
            self.root,
            text="🟢  净化中 — 自动去除 act_",
            bg=BG_PINK,
            fg=TEXT_DARK,
            font=FONT_STATUS,
        )
        self.status_label.pack(pady=(8, 2))

        # ---- 操作提示 ----
        hint = tk.Label(
            self.root,
            text="点击爱心开启 / 关闭净化",
            bg=BG_PINK,
            fg=TEXT_HINT,
            font=FONT_HINT,
        )
        hint.pack(pady=(0, 2))

        # ---- 底部装饰 + 版本信息 ----
        deco_bottom = tk.Frame(self.root, bg=DECO_LINE, height=2)
        deco_bottom.pack(fill="x", side="bottom")

        version_label = tk.Label(
            self.root,
            text="v1.0  |  macOS / Windows",
            bg=BG_PINK,
            fg=TEXT_HINT,
            font=("Arial", 7),
        )
        version_label.pack(side="bottom", pady=(0, 4))

    # ---- 爱心悬停效果 ----

    def _on_heart_enter(self, event):
        """鼠标进入爱心"""
        if self.enabled:
            self.heart_btn.configure(fg=HEART_ON_HOVER)
        else:
            self.heart_btn.configure(fg=HEART_OFF_HOVER)

    def _on_heart_leave(self, event):
        """鼠标离开爱心"""
        if self.enabled:
            self.heart_btn.configure(fg=HEART_ON)
        else:
            self.heart_btn.configure(fg=HEART_OFF)

    # ==================== 开关切换 ====================

    def _toggle(self):
        """切换净化开关"""
        self.enabled = not self.enabled

        if self.enabled:
            self.heart_btn.configure(fg=HEART_ON)
            self.status_label.configure(text="🟢  净化中 — 自动去除 act_")
            print("[ClipSanitizer] 🟢 净化已开启")
        else:
            self.heart_btn.configure(fg=HEART_OFF)
            self.status_label.configure(text="⚪  已暂停 — 点击爱心开启")
            print("[ClipSanitizer] ⚪ 净化已暂停")

        # 点击动画：短暂放大再恢复
        self._click_animation()

    def _click_animation(self):
        """爱心点击缩放动画"""
        original_size = FONT_HEART[1]  # 原始字号
        # 放大
        self.heart_btn.configure(font=(FONT_HEART[0], original_size + 8))
        # 60ms 后恢复
        self.root.after(60, lambda: self.heart_btn.configure(font=FONT_HEART))

    # ==================== 剪贴板轮询 & act_ 处理 ====================

    def _poll(self):
        """定时检查剪贴板内容，检测并处理 act_ 字段"""
        if not self.running:
            return

        if self.enabled and not self.is_modifying:
            try:
                content = self.root.clipboard_get()
                if content:
                    content = content.strip()
                    # 去重：内容和上次一样就直接跳过
                    if content and content != self.last_content:
                        self.last_content = content
                        self._process_content(content)
            except tk.TclError:
                # 剪贴板为空或格式非文本 — 正常情况，忽略
                pass
            except Exception as exc:
                print(f"[ClipSanitizer] 剪贴板读取异常: {exc}")
                self.is_modifying = False

        # 继续下一次轮询
        self.root.after(POLL_INTERVAL, self._poll)

    def _process_content(self, content: str):
        """
        检测内容中是否包含 act_ 标记，
        如果有，去除 act_ 及其之前的所有内容，只保留之后的部分
        """
        if ACT_MARKER not in content:
            return  # 不含 act_，无需处理

        # 找到第一个 act_ 的位置
        idx = content.find(ACT_MARKER)
        # 只保留 act_ 之后的内容 (跳过 "act_" 这 4 个字符)
        new_content = content[idx + len(ACT_MARKER):]

        # 如果处理后内容为空，跳过
        if not new_content:
            print("[ClipSanitizer] ⚠️  act_ 之后无内容，跳过处理")
            return

        # 写入剪贴板
        try:
            self.is_modifying = True
            self.root.clipboard_clear()
            self.root.clipboard_append(new_content)
            self.last_content = new_content
            self.is_modifying = False

            # 日志：显示处理前后的内容摘要
            old_preview = content[:40] + "..." if len(content) > 40 else content
            new_preview = new_content[:40] + "..." if len(new_content) > 40 else new_content
            print(f"[ClipSanitizer] ✅ 已处理 act_")
            print(f"  处理前: {old_preview}")
            print(f"  处理后: {new_preview}")
        except Exception as exc:
            print(f"[ClipSanitizer] ❌ 写入剪贴板失败: {exc}")
            self.is_modifying = False

    # ==================== 生命周期 ====================

    def _on_close(self):
        """关闭窗口时的清理"""
        print("[ClipSanitizer] 正在退出...")
        self.running = False
        self.root.destroy()

    def run(self):
        """启动应用主循环"""
        self.root.mainloop()


# =========================== 入口 ===========================

def main():
    app = ClipboardSanitizer()
    app.run()


if __name__ == "__main__":
    main()
