#!/usr/bin/env python3
"""
Windows 历史剪贴板软件
=======================
- 自动记录文字剪贴板内容
- 按 1天 / 3天 / 7天 分类筛选
- 按时间降序排列，支持置顶
- 搜索功能，实时过滤
- 绿色 UI 主题 (RGB: 214, 248, 55 / #D6F837)

纯 Python 实现，无需安装任何第三方库。
运行方式：python clipboard_history.py
"""

import tkinter as tk
from tkinter import messagebox
import sqlite3
import os
import time
import traceback

# -- 调试日志 --
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clipboard_debug.log")

def _log(msg: str):
    """写调试日志"""
    try:
        stamp = time.strftime("%H:%M:%S", time.localtime())
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {msg}\n")
    except:
        pass

# =========================== 常量 ===========================

# -- 配色方案 --
GREEN_PRIMARY  = "#D6F837"   # 主色调: RGB(214, 248, 55)
GREEN_DARK     = "#B8D42A"   # 深一点的绿色（按钮按下）
GREEN_LIGHT    = "#EFFAD0"   # 浅绿色（置顶高亮背景）
GREEN_PALE     = "#F8FCE8"   # 极浅绿色（列表项悬停）
BG_MAIN        = "#F0F2EB"   # 主窗口背景
BG_WHITE       = "#FFFFFF"   # 卡片/列表项背景
TEXT_DARK      = "#2D2D2D"   # 主文字
TEXT_GRAY      = "#888888"   # 次要文字（时间等）
TEXT_LIGHT     = "#AAAAAA"   # 占位符文字
RED_DELETE     = "#E85D5D"   # 删除按钮
复制
# -- 窗口 --
WINDOW_WIDTH  = 540
WINDOW_HEIGHT = 680
MIN_WIDTH     = 400
MIN_HEIGHT    = 400

# -- 剪贴板轮询间隔（毫秒）--
POLL_INTERVAL = 500

# -- 数据存储 --
DB_DIR  = os.path.expanduser("~/.clipboard_history")
DB_PATH = os.path.join(DB_DIR, "history.db")

# -- 时间筛选档位 --
FILTER_ALL = 0
FILTER_1D  = 1
FILTER_3D  = 3
FILTER_7D  = 7

# =========================== 数据库 ===========================

class Database:
    """SQLite 数据库操作封装"""

    def __init__(self):
        os.makedirs(DB_DIR, exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._init_table()

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS clipboard_items (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                content   TEXT    NOT NULL,
                timestamp REAL   NOT NULL,
                pinned    INTEGER DEFAULT 0
            )
        """)
        # 索引加速排序和筛选
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON clipboard_items(timestamp DESC)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pinned_ts
            ON clipboard_items(pinned, timestamp DESC)
        """)
        self.conn.commit()

    def add_item(self, content: str, timestamp: float) -> int:
        """添加一条记录，返回新记录的 ID"""
        cur = self.conn.execute(
            "INSERT INTO clipboard_items (content, timestamp) VALUES (?, ?)",
            (content, timestamp)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_items(self, days_filter: int = 0, search: str = "") -> list:
        """查询记录列表
        days_filter: 0=全部, 1/3/7=对应天数
        search: 搜索关键词（空字符串=不过滤）
        返回: [(id, content, timestamp, pinned), ...]
        """
        conditions = []
        params = []

        if days_filter > 0:
            cutoff = time.time() - (days_filter * 86400)
            conditions.append("timestamp >= ?")
            params.append(cutoff)

        if search.strip():
            conditions.append("content LIKE ?")
            params.append(f"%{search.strip()}%")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"""
            SELECT id, content, timestamp, pinned
            FROM clipboard_items
            {where}
            ORDER BY pinned DESC, timestamp DESC
        """
        return self.conn.execute(sql, params).fetchall()

    def toggle_pin(self, item_id: int):
        """切换置顶状态（0↔1）"""
        self.conn.execute(
            "UPDATE clipboard_items SET pinned = 1 - pinned WHERE id = ?",
            (item_id,)
        )
        self.conn.commit()

    def delete_item(self, item_id: int):
        self.conn.execute("DELETE FROM clipboard_items WHERE id = ?", (item_id,))
        self.conn.commit()

    def delete_older_than(self, days: int) -> int:
        """删除 N 天前的记录，返回删除条数"""
        cutoff = time.time() - (days * 86400)
        cur = self.conn.execute(
            "DELETE FROM clipboard_items WHERE timestamp < ? AND pinned = 0",
            (cutoff,)
        )
        self.conn.commit()
        return cur.rowcount

    def delete_all(self) -> int:
        """删除全部记录（保留置顶项），返回删除条数"""
        cur = self.conn.execute("DELETE FROM clipboard_items WHERE pinned = 0")
        self.conn.commit()
        return cur.rowcount

    def get_total_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM clipboard_items").fetchone()
        return row[0] if row else 0

    def close(self):
        self.conn.close()


# =========================== 可滚动区域组件 ===========================

class ScrollableFrame(tk.Frame):
    """带滚轮支持的 Canvas + 内部 Frame 组合，用于承载列表项"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=BG_MAIN)

        # Canvas
        self.canvas = tk.Canvas(self, bg=BG_MAIN, highlightthickness=0, bd=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        # 滚动条
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # 内部 Frame —— 所有列表项都放在这里面
        self.inner = tk.Frame(self.canvas, bg=BG_MAIN)
        self._win_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        # 内部 Frame 大小变化 → 更新 Canvas 滚动区域
        self.inner.bind("<Configure>", self._on_inner_configure)
        # Canvas 宽度变化 → 同步内部 Frame 宽度
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # 鼠标滚轮
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

        # 点击空白区域取消"选中"
        self.canvas.bind("<Button-1>", self._on_blank_click)

    def _on_inner_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        # 让内部 Frame 宽度跟随 Canvas
        self.canvas.itemconfig(self._win_id, width=event.width)

    def _on_wheel(self, event):
        """Windows 鼠标滚轮"""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _bind_wheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_blank_click(self, event):
        """点击空白区域时的处理（可扩展）"""
        pass

    def clear(self):
        """清空所有列表项"""
        for w in self.inner.winfo_children():
            w.destroy()

    def scroll_to_top(self):
        self.canvas.yview_moveto(0)


# =========================== 主应用 ===========================

class ClipboardApp:
    """剪贴板历史主程序"""

    def __init__(self):
        # -- 数据库 --
        self.db = Database()

        # -- 当前状态 --
        self.current_filter = FILTER_ALL   # 当前时间筛选
        self.search_text = ""              # 当前搜索词
        self.last_clipboard = ""           # 上一次记录的剪贴板内容（去重用）
        self.is_setting_clipboard = False  # 标记：正在由本程序写入剪贴板
        self.running = True

        # -- 窗口 --
        self.root = tk.Tk()
        self.root.title("历史剪贴板")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.root.configure(bg=BG_MAIN)

        # 窗口图标（尝试设置，失败则忽略）
        try:
            self.root.iconbitmap(default="")
        except:
            pass

        # 关闭窗口时清理
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # -- 构建 UI --
        self._build_ui()

        # -- 加载初始数据 --
        self._refresh_list()

        # -- 启动剪贴板监听 --
        # 清空上次的调试日志
        try:
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                f.write(f"=== 剪贴板监听调试日志 ===\n启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        except:
            pass

        # 先记录当前剪贴板内容，避免把已有内容重复录入
        try:
            self.last_clipboard = self.root.clipboard_get().strip()
            _log(f"初始剪贴板: {self.last_clipboard[:50] if self.last_clipboard else '(空)'}")
        except Exception as e:
            self.last_clipboard = ""
            _log(f"初始剪贴板读取失败: {e}")
        self.poll_count = 0
        self.root.after(500, self._poll_clipboard)
        _log("剪贴板监听已启动")

        # -- 绑定快捷键 --
        self.root.bind("<Control-f>", lambda e: self._focus_search())
        self.root.bind("<Escape>", lambda e: self._clear_search())

    # ==================== UI 构建 ====================

    def _build_ui(self):
        """构建全部界面组件"""
        # -- 标题栏 --
        self._build_title_bar()

        # -- 搜索栏 --
        self._build_search_bar()

        # -- 筛选标签 --
        self._build_filter_tabs()

        # -- 列表区域 --
        self._build_list_area()

        # -- 底部状态栏 --
        self._build_status_bar()

    def _build_title_bar(self):
        """顶部标题栏"""
        bar = tk.Frame(self.root, bg=GREEN_PRIMARY, height=44)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(
            bar, text="📋  历史剪贴板", bg=GREEN_PRIMARY,
            fg=TEXT_DARK, font=("Microsoft YaHei", 13, "bold")
        ).pack(side="left", padx=16, pady=10)

        # 最小化到托盘提示（简化版：最小化按钮）
        self._min_btn = tk.Label(
            bar, text="─", bg=GREEN_PRIMARY, fg=TEXT_DARK,
            font=("Consolas", 14), cursor="hand2"
        )
        self._min_btn.pack(side="right", padx=(0, 8), pady=8)
        self._min_btn.bind("<Button-1>", lambda e: self.root.iconify())

        # 关闭按钮
        close_btn = tk.Label(
            bar, text="✕", bg=GREEN_PRIMARY, fg=TEXT_DARK,
            font=("Arial", 14), cursor="hand2"
        )
        close_btn.pack(side="right", padx=(0, 12), pady=8)
        close_btn.bind("<Button-1>", lambda e: self._on_close())

    def _build_search_bar(self):
        """搜索栏"""
        frame = tk.Frame(self.root, bg=BG_MAIN)
        frame.pack(fill="x", padx=14, pady=(12, 0))

        # 搜索图标
        tk.Label(
            frame, text="🔍", bg=BG_MAIN, font=("Arial", 12)
        ).pack(side="left", padx=(8, 4))

        # 搜索输入框
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._on_search_change())
        self.search_entry = tk.Entry(
            frame, textvariable=self.search_var,
            bg=BG_WHITE, fg=TEXT_DARK, insertbackground=TEXT_DARK,
            font=("Microsoft YaHei", 11), relief="flat", bd=0,
            highlightthickness=1, highlightbackground="#E0E0D0",
            highlightcolor=GREEN_PRIMARY
        )
        self.search_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(4, 4))
        self.search_entry.insert(0, "")

        # 占位符效果
        self._add_placeholder(self.search_entry, "输入关键词搜索...")

        # 清除按钮
        self.clear_search_btn = tk.Label(
            frame, text="✕", bg=BG_WHITE, fg=TEXT_LIGHT,
            font=("Arial", 11), cursor="hand2"
        )
        self.clear_search_btn.pack(side="right", padx=(0, 4), ipadx=4)
        self.clear_search_btn.bind("<Button-1>", lambda e: self._clear_search())
        self.clear_search_btn.bind("<Enter>", lambda e: self.clear_search_btn.configure(fg=RED_DELETE))
        self.clear_search_btn.bind("<Leave>", lambda e: self.clear_search_btn.configure(fg=TEXT_LIGHT))

    def _add_placeholder(self, entry, placeholder):
        """给输入框添加占位符文字效果"""
        def on_focus_in(e):
            if entry.get() == placeholder:
                entry.delete(0, "end")
                entry.configure(fg=TEXT_DARK)

        def on_focus_out(e):
            if not entry.get():
                entry.insert(0, placeholder)
                entry.configure(fg=TEXT_LIGHT)

        # 初始状态
        if not entry.get():
            entry.insert(0, placeholder)
            entry.configure(fg=TEXT_LIGHT)
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

    def _build_filter_tabs(self):
        """时间筛选标签"""
        frame = tk.Frame(self.root, bg=BG_MAIN)
        frame.pack(fill="x", padx=14, pady=(10, 0))

        self.filter_buttons = {}
        filters = [
            (FILTER_ALL, "全部"),
            (FILTER_1D,  "1 天"),
            (FILTER_3D,  "3 天"),
            (FILTER_7D,  "7 天"),
        ]

        for idx, (fid, label) in enumerate(filters):
            btn = tk.Label(
                frame, text=label,
                bg=GREEN_PRIMARY if fid == FILTER_ALL else BG_WHITE,
                fg=TEXT_DARK,
                font=("Microsoft YaHei", 10, "bold"),
                padx=16, pady=6,
                cursor="hand2",
                relief="flat", bd=0
            )
            btn.pack(side="left", padx=(0, 6))
            btn.bind("<Button-1>", lambda e, f=fid: self._on_filter_change(f))
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=GREEN_DARK) if b.cget("bg") != GREEN_PRIMARY else None)
            btn.bind("<Leave>", lambda e, b=btn, f=fid: b.configure(bg=GREEN_PRIMARY if f == self.current_filter else BG_WHITE))
            self.filter_buttons[fid] = btn

    def _build_list_area(self):
        """可滚动的列表区域"""
        outer = tk.Frame(self.root, bg=BG_MAIN)
        outer.pack(fill="both", expand=True, padx=14, pady=(10, 0))

        self.scroll_frame = ScrollableFrame(outer)
        self.scroll_frame.pack(fill="both", expand=True)

    def _build_status_bar(self):
        """底部状态栏"""
        bar = tk.Frame(self.root, bg=BG_MAIN, height=36)
        bar.pack(fill="x", side="bottom", padx=14, pady=(6, 10))
        bar.pack_propagate(False)

        # 记录数
        self.status_label = tk.Label(
            bar, text="共 0 条记录", bg=BG_MAIN,
            fg=TEXT_GRAY, font=("Microsoft YaHei", 9)
        )
        self.status_label.pack(side="left", pady=6)

        # 清空 7 天前
        clear_old_btn = tk.Label(
            bar, text="清空 7 天前", bg=BG_MAIN, fg=TEXT_GRAY,
            font=("Microsoft YaHei", 9), cursor="hand2"
        )
        clear_old_btn.pack(side="right", padx=(10, 4), pady=6)
        clear_old_btn.bind("<Button-1>", lambda e: self._clear_old())
        clear_old_btn.bind("<Enter>", lambda e: clear_old_btn.configure(fg=RED_DELETE))
        clear_old_btn.bind("<Leave>", lambda e: clear_old_btn.configure(fg=TEXT_GRAY))

        # 清空全部
        clear_all_btn = tk.Label(
            bar, text="清空全部", bg=BG_MAIN, fg=TEXT_GRAY,
            font=("Microsoft YaHei", 9), cursor="hand2"
        )
        clear_all_btn.pack(side="right", padx=(6, 0), pady=6)
        clear_all_btn.bind("<Button-1>", lambda e: self._clear_all())
        clear_all_btn.bind("<Enter>", lambda e: clear_all_btn.configure(fg=RED_DELETE))
        clear_all_btn.bind("<Leave>", lambda e: clear_all_btn.configure(fg=TEXT_GRAY))

    # ==================== 列表渲染 ====================

    def _refresh_list(self):
        """从数据库加载数据并重新渲染整个列表"""
        self.scroll_frame.clear()

        # 排除占位符文字，避免占位符被当成搜索词过滤掉所有记录
        search = self.search_var.get().strip()
        if search == "输入关键词搜索...":
            search = ""

        items = self.db.get_items(
            days_filter=self.current_filter,
            search=search
        )

        if not items:
            # 空状态提示
            empty = tk.Label(
                self.scroll_frame.inner, text="📋 暂无记录\n试试复制一些文字吧~",
                bg=BG_MAIN, fg=TEXT_LIGHT,
                font=("Microsoft YaHei", 12),
                justify="center"
            )
            empty.pack(pady=60)
        else:
            for item in items:
                self._render_item(item)

        # 更新状态栏
        total = self.db.get_total_count()
        shown = len(items)
        if self.current_filter == FILTER_ALL and not search:
            self.status_label.configure(text=f"共 {total} 条记录")
        else:
            self.status_label.configure(text=f"显示 {shown} 条  /  共 {total} 条记录")

        # 更新筛选按钮高亮
        for fid, btn in self.filter_buttons.items():
            if fid == self.current_filter:
                btn.configure(bg=GREEN_PRIMARY)
            else:
                btn.configure(bg=BG_WHITE)

    def _render_item(self, item):
        """渲染单条记录为一个列表项卡片"""
        item_id, content, timestamp, pinned = item

        # ---- 卡片容器 ----
        card = tk.Frame(
            self.scroll_frame.inner,
            bg=BG_WHITE if not pinned else GREEN_LIGHT,
            bd=0, highlightthickness=0
        )
        card.pack(fill="x", padx=2, pady=3)

        # 底部细线分隔
        sep = tk.Frame(card, bg="#E8E8E0", height=1)
        sep.pack(side="bottom", fill="x")

        # ---- 卡片内容行 ----
        row = tk.Frame(card, bg=card["bg"])
        row.pack(fill="x", padx=6, pady=6)

        # -- 置顶按钮 --
        pin_char = "★" if pinned else "☆"
        pin_fg   = GREEN_DARK if pinned else TEXT_LIGHT
        pin_btn = tk.Label(
            row, text=pin_char,
            bg=card["bg"], fg=pin_fg,
            font=("Arial", 16), cursor="hand2"
        )
        pin_btn.pack(side="left", padx=(4, 6))
        # 绑定点击
        pin_btn.bind("<Button-1>", lambda e, iid=item_id: self._toggle_pin(iid))
        pin_btn.bind("<Enter>", lambda e, b=pin_btn: b.configure(fg=GREEN_PRIMARY))
        pin_btn.bind("<Leave>", lambda e, b=pin_btn, p=pinned: b.configure(fg=GREEN_DARK if p else TEXT_LIGHT))

        # -- 文本预览 --
        preview = content[:65] + "..." if len(content) > 65 else content
        # 把换行符替换为空格，单行显示更干净
        preview = preview.replace("\n", " ").replace("\r", " ")
        text_label = tk.Label(
            row, text=preview,
            bg=card["bg"], fg=TEXT_DARK,
            font=("Microsoft YaHei", 10),
            anchor="w", justify="left",
            cursor="hand2"
        )
        text_label.pack(side="left", fill="x", expand=True, padx=4)

        # -- 时间 --
        time_str = self._format_time(timestamp)
        time_label = tk.Label(
            row, text=time_str,
            bg=card["bg"], fg=TEXT_GRAY,
            font=("Microsoft YaHei", 8),
            anchor="e"
        )
        time_label.pack(side="right", padx=(6, 2))

        # -- 删除按钮 --
        del_btn = tk.Label(
            row, text="✕",
            bg=card["bg"], fg=TEXT_LIGHT,
            font=("Arial", 12), cursor="hand2"
        )
        del_btn.pack(side="right", padx=(2, 6))
        del_btn.bind("<Button-1>", lambda e, iid=item_id: self._delete_item(iid))
        del_btn.bind("<Enter>", lambda e, b=del_btn: b.configure(fg=RED_DELETE))
        del_btn.bind("<Leave>", lambda e, b=del_btn: b.configure(fg=TEXT_LIGHT))

        # ---- 点击卡片主体 → 复制 ----
        for widget in (card, row, text_label, time_label):
            widget.bind("<Button-1>", lambda e, c=content: self._copy_to_clipboard(c))

        # 右键菜单（在闭包中捕获 content，无需回查数据库）
        card.bind("<Button-3>", lambda e, iid=item_id, p=pinned, c=content: self._show_context_menu(e, iid, p, c))
        for w in (row, text_label, time_label):
            w.bind("<Button-3>", lambda e, iid=item_id, p=pinned, c=content: self._show_context_menu(e, iid, p, c))

        # 悬停效果（只绑到最外层 card，避免内部元素间鼠标移动时闪烁）
        card.bind("<Enter>", lambda e, c=card, p=pinned: c.configure(bg=GREEN_DARK if p else GREEN_PALE))
        card.bind("<Leave>", lambda e, c=card, p=pinned: c.configure(bg=GREEN_LIGHT if p else BG_WHITE))

    # ==================== 时间格式化 ====================

    @staticmethod
    def _format_time(ts: float) -> str:
        """Unix 时间戳转相对时间文本"""
        diff = time.time() - ts
        if diff < 60:
            return "刚刚"
        elif diff < 3600:
            return f"{int(diff // 60)} 分钟前"
        elif diff < 86400:
            return f"{int(diff // 3600)} 小时前"
        elif diff < 259200:  # 3 天内显示天数
            return f"{int(diff // 86400)} 天前"
        else:
            # 超过 3 天显示具体日期
            return time.strftime("%m/%d %H:%M", time.localtime(ts))

    # ==================== 剪贴板监听 ====================

    def _poll_clipboard(self):
        """定时检查剪贴板内容变化（主线程轮询，线程安全）"""
        if not self.running:
            return

        self.poll_count += 1

        if not self.is_setting_clipboard:
            try:
                content = self.root.clipboard_get()
                if content:
                    content = content.strip()
                    if content and content != self.last_clipboard:
                        _log(f"检测到新内容: {content[:50]}...")
                        self.last_clipboard = content
                        self.db.add_item(content, time.time())
                        self._refresh_list()
            except tk.TclError:
                # 剪贴板为空或格式非文本 → 正常情况
                pass
            except Exception as exc:
                _log(f"剪贴板读取异常: {exc}\n{traceback.format_exc()}")

        # 每 20 次轮询写一次状态日志（避免日志刷屏）
        if self.poll_count % 20 == 0:
            _log(f"轮询中 (第{self.poll_count}次)")

        # 继续下一次轮询
        self.root.after(POLL_INTERVAL, self._poll_clipboard)

    # ==================== 交互操作 ====================

    def _on_search_change(self):
        """搜索内容变化时实时刷新列表"""
        # 更新占位符状态
        text = self.search_var.get()
        if text == "输入关键词搜索...":
            return  # 占位符状态，不触发搜索
        self._refresh_list()

    def _clear_search(self):
        """清空搜索（trace 会自动触发 _on_search_change → _refresh_list）"""
        self.search_var.set("")
        self._focus_search()

    def _focus_search(self):
        """聚焦搜索框"""
        self.search_entry.focus_set()
        # 清除占位符
        if self.search_entry.get() == "输入关键词搜索...":
            self.search_entry.delete(0, "end")
            self.search_entry.configure(fg=TEXT_DARK)

    def _on_filter_change(self, fid: int):
        """切换时间筛选"""
        self.current_filter = fid
        self._refresh_list()
        self.scroll_frame.scroll_to_top()

    def _copy_to_clipboard(self, content: str):
        """将内容复制到剪贴板"""
        try:
            self.is_setting_clipboard = True
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.last_clipboard = content  # 避免自身触发重复记录
            self._show_toast("✅  已复制到剪贴板")
        except Exception as e:
            self._show_toast(f"复制失败: {e}")
        finally:
            # 延迟恢复标记，确保剪贴板操作完成
            self.root.after(200, self._reset_clipboard_flag)

    def _reset_clipboard_flag(self):
        self.is_setting_clipboard = False

    def _show_context_menu(self, event, item_id: int, pinned: bool, content: str):
        """右键弹出菜单"""
        menu = tk.Menu(self.root, tearoff=0,
                       bg=BG_WHITE, fg=TEXT_DARK,
                       activebackground=GREEN_PRIMARY, activeforeground=TEXT_DARK,
                       font=("Microsoft YaHei", 10))
        menu.add_command(label="📋 复制", command=lambda: self._copy_to_clipboard(content))
        menu.add_command(
            label="📌 取消置顶" if pinned else "📌 置顶",
            command=lambda: self._toggle_pin(item_id)
        )
        menu.add_separator()
        menu.add_command(label="🗑️ 删除", command=lambda: self._delete_item(item_id))
        menu.post(event.x_root, event.y_root)

    def _toggle_pin(self, item_id: int):
        """切换置顶状态"""
        self.db.toggle_pin(item_id)
        self._refresh_list()

    def _delete_item(self, item_id: int):
        """删除单条记录"""
        self.db.delete_item(item_id)
        self._refresh_list()
        self._show_toast("已删除")

    def _clear_old(self):
        """清空 7 天前的记录"""
        if not messagebox.askyesno("确认", "确定要清空 7 天前的所有记录吗？\n（已置顶的记录不会被删除）"):
            return
        count = self.db.delete_older_than(7)
        self._refresh_list()
        self._show_toast(f"已清空 {count} 条记录")

    def _clear_all(self):
        """清空全部记录"""
        if not messagebox.askyesno("确认", "确定要清空全部记录吗？\n（已置顶的记录不会被删除）"):
            return
        count = self.db.delete_all()
        self._refresh_list()
        self._show_toast(f"已清空 {count} 条记录")

    def _show_toast(self, message: str):
        """在状态栏短暂显示提示，之后恢复原来的计数"""
        original_text = self.status_label.cget("text")
        self.status_label.configure(text=message)
        self.root.after(2500, lambda: self.status_label.configure(text=original_text))

    # ==================== 生命周期 ====================

    def _on_close(self):
        """窗口关闭时的清理"""
        self.running = False
        self.db.close()
        self.root.destroy()

    def run(self):
        """启动应用"""
        self.root.mainloop()


# =========================== 入口 ===========================

def main():
    app = ClipboardApp()
    app.run()


if __name__ == "__main__":
    main()
