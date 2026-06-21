#!/usr/bin/env python3
"""
工单 act_ 账户计数工具
======================
- 读取 Excel/CSV 文件中的工单编号
- 自动到 medialhub 查询每个工单详情中的 act_ 账户数量
- 汇总结果 + 一键复制
- macOS .app / Windows 均可运行

纯 Python 实现。运行方式：python workorder_act_counter.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sys
import os
import re
import csv
import io
import json
import threading
import queue
import time
import platform
import traceback
from pathlib import Path
from datetime import datetime

# =========================== 平台检测 ===========================

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

# =========================== 日志文件 ===========================

LOG_FILE = None  # PyInstaller --windowed 无控制台，写日志到文件

def log(msg):
    """写日志到文件（供调试用）"""
    global LOG_FILE
    if LOG_FILE is None:
        log_dir = os.path.expanduser("~")
        LOG_FILE = open(os.path.join(log_dir, "workorder_act_counter.log"), "a", encoding="utf-8")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LOG_FILE.write(f"[{ts}] {msg}\n")
    LOG_FILE.flush()

# =========================== 可选依赖检测 ===========================

HAS_PLAYWRIGHT = False
HAS_OPENPYXL = False
HAS_XLRD = False

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    pass

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    pass

try:
    import xlrd
    HAS_XLRD = True
except ImportError:
    pass

# =========================== 资源路径 ===========================

def resource_path(relative):
    """获取资源文件路径，兼容 PyInstaller 打包 + .app Resources"""
    if getattr(sys, 'frozen', False):
        bundled = os.path.join(sys._MEIPASS, relative)
        if os.path.exists(bundled):
            return bundled

        exe_dir = os.path.dirname(sys.executable)
        app_resources = os.path.join(exe_dir, '..', 'Resources', relative)
        app_resources = os.path.normpath(app_resources)
        if os.path.exists(app_resources):
            return app_resources

        fallback = os.path.join(exe_dir, relative)
        if os.path.exists(fallback):
            return fallback

        return bundled

    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative)

# =========================== 配色 (清新风格) ===========================

BG_MAIN       = "#F5F0F5"   # 主背景
BG_FRAME      = "#FFFFFF"   # 卡片背景
ACCENT        = "#E8B4B8"   # 粉色强调
ACCENT_DARK   = "#D4919E"   # 深粉
TEXT_DARK      = "#4A3040"   # 深色文字
TEXT_HINT      = "#B8A0A8"   # 提示文字
TEXT_SUCCESS   = "#5B8C5A"   # 成功绿
TEXT_ERROR     = "#C45C5C"   # 错误红
PROGRESS_BG    = "#F0E0E5"   # 进度条背景
BTN_BG         = "#E8B4B8"   # 按钮背景
BTN_ACTIVE     = "#D4919E"   # 按钮按下
BTN_COPY       = "#D4C5A9"   # 复制按钮

# =========================== 字体 ===========================

if IS_MAC:
    FONT_TITLE   = ("PingFang SC", 14, "bold")
    FONT_LABEL   = ("PingFang SC", 11)
    FONT_BTN     = ("PingFang SC", 11)
    FONT_STATUS  = ("PingFang SC", 10)
    FONT_TABLE   = ("PingFang SC", 10)
    FONT_HINT    = ("PingFang SC", 9)
else:
    FONT_TITLE   = ("Microsoft YaHei", 13, "bold")
    FONT_LABEL   = ("Microsoft YaHei", 11)
    FONT_BTN     = ("Microsoft YaHei", 11)
    FONT_STATUS  = ("Microsoft YaHei", 10)
    FONT_TABLE   = ("Microsoft YaHei", 10)
    FONT_HINT    = ("Microsoft YaHei", 9)

# =========================== 窗口尺寸 ===========================

WINDOW_WIDTH  = 680
WINDOW_HEIGHT = 600

# =========================== 文件读取 ===========================

def read_workorder_numbers(file_path, filter_text=None):
    """
    读取文件第一列（工单编号），可选按第二列过滤。
    支持 .csv / .xlsx / .xls
    返回: (工单编号列表, 错误信息)
    """
    ext = os.path.splitext(file_path)[1].lower()
    rows = []

    try:
        if ext == '.csv':
            rows = _read_csv(file_path)
        elif ext in ('.xlsx', '.xlsm'):
            if not HAS_OPENPYXL:
                return None, "需要 openpyxl 库读取 .xlsx 文件\n请运行: pip install openpyxl"
            rows = _read_xlsx(file_path)
        elif ext == '.xls':
            if not HAS_XLRD:
                return None, "需要 xlrd 库读取 .xls 文件\n请运行: pip install xlrd"
            rows = _read_xls(file_path)
        else:
            return None, f"不支持的文件格式: {ext}\n支持: .csv / .xlsx / .xls"
    except Exception as e:
        return None, f"读取文件失败: {str(e)}"

    if not rows:
        return None, "文件中没有数据行"

    # 检查第一行是否是表头
    first_cell = rows[0][0].strip() if rows[0] else ""
    header_keywords = ["工单编号", "工单号", "编号", "ID", "id", "workorder", "ticket"]
    has_header = any(kw in first_cell for kw in header_keywords)

    data_start = 1 if has_header else 0
    log(f"检测到表头={has_header}, 数据从第{data_start+1}行开始, 共{len(rows)}行")

    results = []
    for i in range(data_start, len(rows)):
        row = rows[i]
        if not row or not row[0]:
            continue

        order_id = str(row[0]).strip()
        if not order_id:
            continue

        # 可选：按第二列过滤
        if filter_text and len(row) >= 2:
            col2 = str(row[1]).strip() if row[1] else ""
            if filter_text not in col2:
                continue

        results.append(order_id)

    return results, None


def _read_csv(file_path):
    """读取 CSV 文件"""
    rows = []
    # 尝试多种编码
    for enc in ['utf-8', 'utf-8-sig', 'gbk', 'gb18030', 'gb2312', 'latin-1']:
        try:
            with open(file_path, 'r', encoding=enc, newline='') as f:
                reader = csv.reader(f)
                rows = list(reader)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception:
            break
    return rows


def _read_xlsx(file_path):
    """读取 .xlsx 文件"""
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(min_row=1, values_only=True):
        rows.append([str(cell) if cell is not None else "" for cell in row])
    wb.close()
    return rows


def _read_xls(file_path):
    """读取 .xls 文件"""
    wb = xlrd.open_workbook(file_path)
    ws = wb.sheet_by_index(0)
    rows = []
    for r in range(ws.nrows):
        row = []
        for c in range(ws.ncols):
            cell = ws.cell_value(r, c)
            row.append(str(cell) if cell else "")
        rows.append(row)
    return rows

# =========================== medalhub 自动化 ===========================

class MedialhubAutomator:
    """使用 Playwright 自动操作 medialhub 网页"""

    def __init__(self, headless=True):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self._playwright = None
        self.base_url = "https://mediahub.meetsocial.cn"
        self.list_url = f"{self.base_url}/account/workorder"

    def start(self):
        """启动浏览器 — 优先用系统 Chrome，无需额外下载"""
        log("启动浏览器...")
        self._playwright = sync_playwright().start()

        launch_kwargs = {"headless": self.headless}

        # 优先级: 系统Chrome > 系统Edge > Playwright Chromium > 错误提示
        browser_method, browser_name = self._pick_browser()

        if browser_method == "channel":
            launch_kwargs["channel"] = browser_name
            log(f"使用系统浏览器: {browser_name}")
        elif browser_method == "executable":
            launch_kwargs["executable_path"] = browser_name
            log(f"使用浏览器: {browser_name}")
        elif browser_method == "error":
            raise RuntimeError(browser_name)

        self.browser = self._playwright.chromium.launch(**launch_kwargs)
        self.context = self.browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        self.page = self.context.new_page()
        self.page.set_default_timeout(30000)
        log(f"浏览器启动成功 ({browser_name})")

    def _pick_browser(self):
        """选择可用的浏览器，返回 (方式, 名称)"""
        # 1) 系统 Google Chrome（最优先，你的Mac大概率有）
        chrome_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        for p in chrome_paths:
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return ("executable", p)

        # 2) 系统 Microsoft Edge
        edge_paths = [
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
            "/usr/bin/microsoft-edge",
        ]
        for p in edge_paths:
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return ("executable", p)

        # 3) Playwright 自带的 Chromium（如果之前安装过）
        for cache_dir in [
            os.path.expanduser("~/Library/Caches/ms-playwright"),
            os.path.expanduser("~/.cache/ms-playwright"),
            os.path.expandvars(r"%USERPROFILE%\AppData\Local\ms-playwright"),
        ]:
            if os.path.isdir(cache_dir):
                for root, dirs, files in os.walk(cache_dir):
                    if IS_MAC and "Chromium.app" in dirs:
                        p = os.path.join(root, "Chromium.app", "Contents", "MacOS", "Chromium")
                        if os.path.isfile(p):
                            return ("executable", p)
                    elif IS_WIN and "chrome.exe" in files:
                        return ("executable", os.path.join(root, "chrome.exe"))

        # 4) 都没有 → 报错
        msg = (
            "未找到可用的浏览器。\n\n"
            "请安装 Google Chrome 浏览器:\n"
            "https://www.google.com/chrome/\n\n"
            "安装后重新打开本程序即可。"
        )
        return ("error", msg)

    def check_login(self):
        """检查是否已登录，返回 (is_logged_in, 提示信息)"""
        log("检查登录状态...")
        try:
            self.page.goto(self.list_url, wait_until="networkidle", timeout=20000)
            self.page.wait_for_timeout(2000)  # 等页面 JS 渲染完

            content = self.page.content()

            # 检查常见的登录相关元素
            login_indicators = [
                "login",
                "Login",
                "登录",
                "signin",
                "SignIn",
                "password",
                "Password",
                "请输入密码",
            ]

            found_login = []
            for indicator in login_indicators:
                try:
                    if self.page.locator(f"text={indicator}").count() > 0:
                        found_login.append(indicator)
                except:
                    pass

            # 也检查 URL 是否被重定向到登录页
            current_url = self.page.url.lower()
            if "login" in current_url or "signin" in current_url or "auth" in current_url:
                log(f"URL 包含登录关键词: {current_url}")
                return False, "检测到登录页面，请先在浏览器中登录 medialhub"

            if found_login:
                log(f"页面包含登录元素: {found_login}")
                return False, f"检测到登录表单，请先在浏览器中登录 medialhub"

            # 检查是否能找到工单列表页面元素
            has_workorder_content = False
            try:
                has_workorder_content = (
                    self.page.locator("text=工单").count() > 0 or
                    self.page.locator("text=媒体工单").count() > 0 or
                    self.page.locator("text=账号").count() > 0
                )
            except:
                pass

            if has_workorder_content:
                log("登录状态: 已登录 ✓")
                return True, "已登录"
            else:
                # 既没找到登录也没找到工单内容 —— 可能页面加载不完全
                log("警告: 未检测到登录或工单内容，尝试继续...")
                return True, "未明确检测到登录状态，继续尝试"

        except Exception as e:
            log(f"检查登录失败: {e}")
            return False, f"无法访问 medialhub: {str(e)}"

    def query_one(self, order_id, start_date, end_date):
        """
        查询一个工单的 act_ 账户数。
        返回: {"order_id": str, "act_count": int, "status": str, "error": str|None}
        """
        result = {
            "order_id": order_id,
            "act_count": 0,
            "status": "成功",
            "error": None,
        }

        try:
            # ---- 第1步: 回到工单列表页 ----
            log(f"[{order_id}] 进入工单列表页...")
            try:
                self.page.goto(self.list_url, wait_until="networkidle", timeout=20000)
            except:
                # 超时也继续
                pass
            self.page.wait_for_timeout(1500)

            # ---- 第2步: 填入日期 ----
            log(f"[{order_id}] 填入日期: {start_date} ~ {end_date}")
            self._fill_date_fields(start_date, end_date)

            # ---- 第3步: 填入工单编号并搜索 ----
            log(f"[{order_id}] 填入工单编号并搜索...")
            self._fill_order_id_and_search(order_id)

            # ---- 第4步: 等待搜索结果 ----
            self.page.wait_for_timeout(2000)

            # ---- 第5步: 点击进入工单详情 ----
            log(f"[{order_id}] 进入工单详情...")
            detail_opened = self._click_order_detail(order_id)

            if not detail_opened:
                result["status"] = "未找到"
                result["error"] = "无法打开工单详情"
                return result

            # ---- 第6步: 统计 act_ 账户 ----
            self.page.wait_for_timeout(1500)
            act_count = self._count_act_accounts()
            result["act_count"] = act_count
            log(f"[{order_id}] act_ 账户数: {act_count}")

        except Exception as e:
            result["status"] = "失败"
            result["error"] = str(e)[:200]
            log(f"[{order_id}] 出错: {e}")

        return result

    def _fill_date_fields(self, start_date, end_date):
        """尝试填入日期范围"""
        # 策略1: 找日期输入框
        date_inputs = self.page.locator('input[type="date"], input[type="text"]').all()
        date_related = []

        for inp in date_inputs:
            try:
                placeholder = (inp.get_attribute("placeholder") or "").lower()
                name = (inp.get_attribute("name") or "").lower()
                label_text = ""
                # 尝试获取关联 label
                try:
                    parent = inp.locator("..")
                    label_text = parent.inner_text()
                except:
                    pass

                if any(kw in placeholder or kw in name or kw in label_text
                       for kw in ["开始", "start", "结束", "end", "日期", "date", "时间", "time", "提交", "创建"]):
                    date_related.append(inp)
            except:
                pass

        log(f"找到 {len(date_related)} 个日期相关输入框")

        # 尝试按顺序填入开始和结束日期
        if len(date_related) >= 2:
            try:
                date_related[0].click()
                date_related[0].fill("")
                date_related[0].type(start_date, delay=50)
                self.page.wait_for_timeout(300)
                date_related[1].click()
                date_related[1].fill("")
                date_related[1].type(end_date, delay=50)
                self.page.wait_for_timeout(300)
                return
            except Exception as e:
                log(f"填入日期失败(策略1): {e}")

        # 策略2: 尝试用键盘 Tab 切换
        if len(date_related) >= 1:
            try:
                date_related[0].click()
                date_related[0].fill(start_date)
                self.page.keyboard.press("Tab")
                self.page.wait_for_timeout(200)
                # 在当前焦点元素输入结束日期
                self.page.keyboard.type(end_date, delay=50)
                return
            except Exception as e:
                log(f"填入日期失败(策略2): {e}")

        # 策略3: 通过标签文字找
        try:
            self.page.locator('text=/开始.*日期|开始.*时间|start/i').locator("..").locator("input").first.fill(start_date)
            self.page.locator('text=/结束.*日期|结束.*时间|end/i').locator("..").locator("input").first.fill(end_date)
        except Exception as e:
            log(f"填入日期失败(策略3): {e}")

    def _fill_order_id_and_search(self, order_id):
        """填入工单编号并点击查询"""
        # 策略1: 找工单编号输入框
        search_input = None
        for sel in [
            'input[placeholder*="工单"]',
            'input[placeholder*="编号"]',
            'input[placeholder*="搜索"]',
            'input[placeholder*="search"]',
            'input[name*="order"]',
            'input[name*="ticket"]',
            'input[name*="work"]',
        ]:
            try:
                el = self.page.locator(sel).first
                if el.count() > 0:
                    search_input = el
                    break
            except:
                continue

        # 策略2: 通过标签找
        if search_input is None:
            try:
                search_input = self.page.locator('text=/工单.*编号|工单号|工单/i').locator("..").locator("input").first
            except:
                pass

        # 策略3: 找任意搜索框
        if search_input is None:
            try:
                all_inputs = self.page.locator('input[type="text"], input:not([type])').all()
                if all_inputs:
                    search_input = all_inputs[0]  # 第一个文本输入框
            except:
                pass

        if search_input:
            search_input.click()
            search_input.fill("")
            search_input.type(order_id, delay=30)
            self.page.wait_for_timeout(300)

        # 点击查询按钮
        search_clicked = False
        for sel in [
            'button:has-text("查询")',
            'button:has-text("搜索")',
            'button:has-text("Search")',
            'a:has-text("查询")',
            'span:has-text("查询")',
            '.ant-btn:has-text("查询")',
            '[type="submit"]',
        ]:
            try:
                btn = self.page.locator(sel).first
                if btn.count() > 0:
                    btn.click()
                    search_clicked = True
                    break
            except:
                continue

        # 如果没找到按钮，尝试回车
        if not search_clicked:
            try:
                self.page.keyboard.press("Enter")
            except:
                pass

    def _click_order_detail(self, order_id):
        """在搜索结果中点击工单详情"""
        # 等待表格/列表加载
        self.page.wait_for_timeout(1000)

        # 策略1: 点击包含工单编号的链接
        try:
            link = self.page.locator(f'text={order_id}').first
            if link.count() > 0:
                link.click()
                self.page.wait_for_timeout(1500)
                return True
        except:
            pass

        # 策略2: 点击工单编号所在的整行
        try:
            # 找包含工单编号的行
            row = self.page.locator(f'tr:has-text("{order_id}")').first
            if row.count() > 0:
                row.click()
                self.page.wait_for_timeout(1500)
                return True
        except:
            pass

        # 策略3: 点击包含工单编号的任意可点击元素
        try:
            clickable = self.page.locator(f'a:has-text("{order_id}"), [class*="link"]:has-text("{order_id}")').first
            if clickable.count() > 0:
                clickable.click()
                self.page.wait_for_timeout(1500)
                return True
        except:
            pass

        # 策略4: 找详情/查看 按钮
        log(f"[{order_id}] 无法直接点击工单编号，尝试找详情按钮...")
        try:
            # 先点工单所在行，再找详情按钮
            row = self.page.locator(f'tr:has-text("{order_id}"), [class*="row"]:has-text("{order_id}")').first
            if row.count() > 0:
                detail_btn = row.locator('text=/详情|查看|detail|view/i').first
                if detail_btn.count() > 0:
                    detail_btn.click()
                    self.page.wait_for_timeout(1500)
                    return True
        except:
            pass

        log(f"[{order_id}] 所有策略均无法打开工单详情")
        return False

    def _count_act_accounts(self):
        """在工单详情页统计 act_ 开头的账户数量"""
        page_text = ""
        try:
            page_text = self.page.inner_text("body")
        except:
            try:
                page_text = self.page.content()
            except:
                pass

        # 查找所有 act_ 开头的词（账户ID）
        # 匹配 act_ 后跟数字/字母/下划线的组合
        pattern = r'act_[a-zA-Z0-9_]+'
        matches = re.findall(pattern, page_text)

        # 去重
        unique = list(set(matches))
        count = len(unique)

        log(f"  找到 act_ 账户: {unique}")
        return count

    def stop(self):
        """关闭浏览器"""
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self._playwright:
                self._playwright.stop()
        except:
            pass
        log("浏览器已关闭")

# =========================== 主界面 ===========================

class WorkorderActCounterApp:
    """工单 act_ 账户计数工具 主应用"""

    def __init__(self):
        self.workorder_list = []
        self.results = []
        self.is_running = False
        self.stop_requested = False
        self.result_queue = queue.Queue()
        self.automator = None

        # ---- 窗口 ----
        self.root = tk.Tk()
        self.root.title("工单 act_ 账户计数工具")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(580, 480)
        self.root.configure(bg=BG_MAIN)

        # 窗口图标
        try:
            self.root.iconbitmap(default="")
        except:
            pass

        # ---- 构建 UI ----
        self._build_ui()

        # ---- 定期检查结果队列 ----
        self._poll_queue()

        # ---- 关闭处理 ----
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ==================== UI 构建 ====================

    def _build_ui(self):
        """构建全部界面组件"""

        # ===== 标题 =====
        title_frame = tk.Frame(self.root, bg=BG_MAIN)
        title_frame.pack(pady=(16, 8))

        tk.Label(
            title_frame,
            text="📋  工单 act_ 账户计数工具",
            font=FONT_TITLE,
            fg=TEXT_DARK,
            bg=BG_MAIN,
        ).pack()

        tk.Label(
            title_frame,
            text="自动查询 medialhub 工单详情中的 act_ 账户数量",
            font=FONT_HINT,
            fg=TEXT_HINT,
            bg=BG_MAIN,
        ).pack(pady=(2, 0))

        # ===== 设置卡片 =====
        card = tk.Frame(self.root, bg=BG_FRAME, highlightthickness=1,
                        highlightbackground="#E8D8DC", highlightcolor="#E8D8DC")
        card.pack(fill="x", padx=24, pady=(4, 8))

        card_inner = tk.Frame(card, bg=BG_FRAME)
        card_inner.pack(padx=20, pady=(14, 10), fill="x")

        # -- 第1行: 日期范围 --
        row1 = tk.Frame(card_inner, bg=BG_FRAME)
        row1.pack(fill="x", pady=3)

        tk.Label(row1, text="开始日期:", font=FONT_LABEL, fg=TEXT_DARK,
                 bg=BG_FRAME, width=9, anchor="e").pack(side="left")
        self.start_date_var = tk.StringVar(value="")
        self.start_date_entry = tk.Entry(row1, textvariable=self.start_date_var,
                                          font=FONT_LABEL, width=14,
                                          relief="solid", borderwidth=1)
        self.start_date_entry.pack(side="left", padx=(4, 0))
        # 占位提示
        self._set_placeholder(self.start_date_entry, "2026/6/13")

        tk.Label(row1, text="  结束日期:", font=FONT_LABEL, fg=TEXT_DARK,
                 bg=BG_FRAME).pack(side="left")
        self.end_date_var = tk.StringVar(value="")
        self.end_date_entry = tk.Entry(row1, textvariable=self.end_date_var,
                                        font=FONT_LABEL, width=14,
                                        relief="solid", borderwidth=1)
        self.end_date_entry.pack(side="left", padx=(4, 0))
        self._set_placeholder(self.end_date_entry, "2026/6/19")

        # -- 第2行: 文件选择 --
        row2 = tk.Frame(card_inner, bg=BG_FRAME)
        row2.pack(fill="x", pady=3)

        tk.Label(row2, text="选择文件:", font=FONT_LABEL, fg=TEXT_DARK,
                 bg=BG_FRAME, width=9, anchor="e").pack(side="left")

        self.file_var = tk.StringVar(value="")
        file_entry = tk.Entry(row2, textvariable=self.file_var,
                              font=FONT_LABEL, relief="solid", borderwidth=1,
                              state="readonly", readonlybackground="white")
        file_entry.pack(side="left", fill="x", expand=True, padx=(4, 0))

        self.browse_btn = tk.Button(row2, text="浏览...", font=FONT_BTN,
                                     bg=BTN_BG, fg="white", activebackground=BTN_ACTIVE,
                                     activeforeground="white", relief="flat",
                                     padx=14, pady=2, cursor="hand2",
                                     command=self._browse_file)
        self.browse_btn.pack(side="left", padx=(6, 0))

        # -- 第3行: 问题类型过滤 --
        row3 = tk.Frame(card_inner, bg=BG_FRAME)
        row3.pack(fill="x", pady=3)

        tk.Label(row3, text="问题类型:", font=FONT_LABEL, fg=TEXT_DARK,
                 bg=BG_FRAME, width=9, anchor="e").pack(side="left")
        self.filter_var = tk.StringVar(value="绑定/解绑BM报错重试")
        self.filter_entry = tk.Entry(row3, textvariable=self.filter_var,
                                      font=FONT_LABEL, relief="solid", borderwidth=1)
        self.filter_entry.pack(side="left", padx=(4, 0))
        tk.Label(row3, text="（留空 = 读取全部）", font=FONT_HINT,
                 fg=TEXT_HINT, bg=BG_FRAME).pack(side="left", padx=(8, 0))

        # ===== 操作按钮行 =====
        btn_row = tk.Frame(self.root, bg=BG_MAIN)
        btn_row.pack(pady=(4, 6))

        self.start_btn = tk.Button(btn_row, text="▶  开始查询", font=FONT_BTN,
                                    bg=BTN_BG, fg="white", activebackground=BTN_ACTIVE,
                                    activeforeground="white", relief="flat",
                                    padx=24, pady=4, cursor="hand2",
                                    command=self._start_query)
        self.start_btn.pack(side="left", padx=4)

        self.stop_btn = tk.Button(btn_row, text="⏹  停止", font=FONT_BTN,
                                   bg="#C0C0C0", fg="white", activebackground="#A0A0A0",
                                   activeforeground="white", relief="flat",
                                   padx=24, pady=4, cursor="hand2",
                                   command=self._stop_query, state="disabled")
        self.stop_btn.pack(side="left", padx=4)

        # ===== 进度区域 =====
        self.progress_frame = tk.Frame(self.root, bg=BG_MAIN)
        self.progress_frame.pack(fill="x", padx=24, pady=(2, 4))

        self.progress_bar = ttk.Progressbar(self.progress_frame, length=100, mode="determinate")
        self.progress_bar.pack(fill="x")

        self.status_var = tk.StringVar(value="就绪 — 选择文件后点击「开始查询」")
        tk.Label(self.progress_frame, textvariable=self.status_var,
                 font=FONT_STATUS, fg=TEXT_HINT, bg=BG_MAIN).pack(pady=(2, 0))

        # ===== 结果表格 =====
        table_frame = tk.Frame(self.root, bg=BG_FRAME, highlightthickness=1,
                               highlightbackground="#E8D8DC")
        table_frame.pack(fill="both", expand=True, padx=24, pady=(2, 6))

        # Treeview 表格
        columns = ("order_id", "act_count", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings",
                                  height=10, selectmode="extended")

        self.tree.heading("order_id", text="工单编号")
        self.tree.heading("act_count", text="act_ 账户数")
        self.tree.heading("status", text="状态")

        self.tree.column("order_id", width=280, anchor="w")
        self.tree.column("act_count", width=100, anchor="center")
        self.tree.column("status", width=80, anchor="center")

        # 滚动条
        tree_scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set)

        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll_y.pack(side="right", fill="y")

        # 表格右键菜单
        self.tree_menu = tk.Menu(self.root, tearoff=0)
        self.tree_menu.add_command(label="复制选中行", command=self._copy_selected)
        self.tree.bind("<Button-3>" if IS_WIN else "<Button-2>",
                        self._show_tree_menu)

        # ===== 底部按钮 =====
        bottom_row = tk.Frame(self.root, bg=BG_MAIN)
        bottom_row.pack(pady=(0, 12))

        self.copy_btn = tk.Button(bottom_row, text="📋  一键复制全部结果", font=FONT_BTN,
                                   bg=BTN_COPY, fg="white", activebackground="#C0B098",
                                   activeforeground="white", relief="flat",
                                   padx=20, pady=4, cursor="hand2",
                                   command=self._copy_all)
        self.copy_btn.pack(side="left", padx=4)

        self.clear_btn = tk.Button(bottom_row, text="清空结果", font=FONT_BTN,
                                    bg="#E0E0E0", fg=TEXT_DARK, activebackground="#D0D0D0",
                                    relief="flat", padx=16, pady=4, cursor="hand2",
                                    command=self._clear_results)
        self.clear_btn.pack(side="left", padx=4)

        # 统计标签
        self.summary_var = tk.StringVar(value="")
        tk.Label(bottom_row, textvariable=self.summary_var,
                 font=FONT_HINT, fg=TEXT_HINT, bg=BG_MAIN).pack(side="left", padx=(16, 0))

        # ===== 依赖检测提示 =====
        if not HAS_PLAYWRIGHT:
            self._show_dependency_warning()

    def _show_dependency_warning(self):
        """显示依赖缺失警告"""
        missing = []
        if not HAS_PLAYWRIGHT:
            missing.append("playwright")
        if not HAS_OPENPYXL:
            missing.append("openpyxl")
        if not HAS_XLRD:
            missing.append("xlrd")

        if missing:
            msg = f"⚠️  缺少依赖库: {', '.join(missing)}\n\n请运行以下命令安装:\npip install {' '.join(missing)}\nplaywright install chromium"
            messagebox.showwarning("依赖缺失", msg)

    def _set_placeholder(self, entry, placeholder_text):
        """给 Entry 设置占位文字效果"""
        def on_focus_in(e):
            if entry.get() == placeholder_text:
                entry.delete(0, "end")
                entry.config(fg=TEXT_DARK)
        def on_focus_out(e):
            if entry.get() == "":
                entry.insert(0, placeholder_text)
                entry.config(fg=TEXT_HINT)
        entry.insert(0, placeholder_text)
        entry.config(fg=TEXT_HINT)
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

    # ==================== 操作逻辑 ====================

    def _browse_file(self):
        """选择文件"""
        file_path = filedialog.askopenfilename(
            title="选择工单文件",
            filetypes=[
                ("Excel / CSV 文件", "*.csv *.xlsx *.xls"),
                ("CSV 文件", "*.csv"),
                ("Excel 文件", "*.xlsx *.xls"),
                ("所有文件", "*.*"),
            ],
        )
        if file_path:
            self.file_var.set(file_path)

    def _start_query(self):
        """开始查询"""
        if self.is_running:
            return

        # ---- 验证输入 ----
        file_path = self.file_var.get().strip()
        if not file_path:
            messagebox.showwarning("提示", "请先选择文件")
            return

        if not os.path.exists(file_path):
            messagebox.showerror("错误", f"文件不存在:\n{file_path}")
            return

        start_date = self._get_date_value(self.start_date_var, self.start_date_entry)
        end_date = self._get_date_value(self.end_date_var, self.end_date_entry)

        if not start_date or not end_date:
            messagebox.showwarning("提示", "请填写开始日期和结束日期")
            return

        # ---- 检查依赖 ----
        if not HAS_PLAYWRIGHT:
            messagebox.showerror("缺少依赖",
                "需要 Playwright 库来操作网页。\n\n"
                "请运行:\n"
                "pip install playwright\n"
                "playwright install chromium")
            return

        # ---- 读取文件 ----
        filter_text = self.filter_var.get().strip()
        if not filter_text:
            filter_text = None

        self.status_var.set("正在读取文件...")
        self.root.update()

        workorders, error = read_workorder_numbers(file_path, filter_text)

        if error:
            messagebox.showerror("读取文件失败", error)
            self.status_var.set("就绪 — 选择文件后点击「开始查询」")
            return

        if not workorders:
            messagebox.showwarning("提示", "文件中没有找到符合条件的工单编号")
            self.status_var.set("就绪 — 选择文件后点击「开始查询」")
            return

        self.workorder_list = workorders
        log(f"读取到 {len(workorders)} 个工单编号")

        # 去重
        self.workorder_list = list(dict.fromkeys(self.workorder_list))
        if len(self.workorder_list) < len(workorders):
            log(f"去重后剩余 {len(self.workorder_list)} 个")

        # ---- 清空旧结果 ----
        self._clear_results()

        # ---- 开始后台任务 ----
        self.is_running = True
        self.stop_requested = False
        self.start_btn.config(state="disabled", bg="#C0C0C0")
        self.stop_btn.config(state="normal", bg="#E07070", activebackground="#D05050")
        self.browse_btn.config(state="disabled")
        self.progress_bar["maximum"] = len(self.workorder_list)
        self.progress_bar["value"] = 0

        thread = threading.Thread(target=self._run_automation_thread,
                                  args=(start_date, end_date), daemon=True)
        thread.start()

    def _get_date_value(self, var, entry):
        """获取日期值，跳过placeholder"""
        val = var.get().strip()
        if val in ("", "2026/6/13", "2026/6/19"):
            # 检查焦点
            return val if val and "/" in val else ""
        return val

    def _stop_query(self):
        """停止查询"""
        if self.is_running:
            self.stop_requested = True
            self.status_var.set("正在停止...")
            self.stop_btn.config(state="disabled")

    def _run_automation_thread(self, start_date, end_date):
        """在后台线程中运行 Playwright 自动化"""
        automator = None
        try:
            automator = MedialhubAutomator(headless=True)

            # 启动浏览器
            self._queue_status("正在启动浏览器...")
            automator.start()

            # 检查登录
            self._queue_status("正在检查登录状态...")
            is_logged_in, login_msg = automator.check_login()

            if not is_logged_in:
                self._queue_error(login_msg)
                automator.stop()
                self._queue_done()
                return

            self._queue_status(f"✓ 已登录，开始查询 {len(self.workorder_list)} 个工单...")

            total = len(self.workorder_list)
            success_count = 0
            fail_count = 0

            for i, order_id in enumerate(self.workorder_list):
                if self.stop_requested:
                    self._queue_status("已停止")
                    self._add_result({"order_id": "---", "act_count": "---", "status": "已停止"})
                    break

                progress = i + 1
                self._queue_status(f"正在查询: 第 {progress}/{total} 个 — {order_id}")
                self._queue_progress(progress)

                # 查询单个工单（最多重试2次）
                result = None
                for attempt in range(3):
                    if self.stop_requested:
                        break
                    result = automator.query_one(order_id, start_date, end_date)
                    if result["status"] == "成功":
                        break
                    if attempt < 2:
                        self._queue_status(f"  重试 {attempt+2}/3: {order_id}")
                        time.sleep(2)

                if result:
                    if result["status"] == "成功":
                        success_count += 1
                    else:
                        fail_count += 1
                    self._add_result(result)
                    self._queue_summary(success_count, fail_count, total)

                # 请求间短暂延迟
                time.sleep(0.5)

            self._queue_status(f"查询完成！成功: {success_count}, 失败: {fail_count}")
            self._queue_done()

        except Exception as e:
            log(f"自动化线程崩溃: {e}\n{traceback.format_exc()}")
            self._queue_error(f"程序异常: {str(e)[:150]}")
            self._queue_done()
        finally:
            if automator:
                try:
                    automator.stop()
                except:
                    pass

    # ---- 线程安全的结果传递 ----

    def _queue_status(self, msg):
        self.result_queue.put(("status", msg))

    def _queue_progress(self, val):
        self.result_queue.put(("progress", val))

    def _add_result(self, result):
        self.result_queue.put(("result", result))

    def _queue_summary(self, success, fail, total):
        self.result_queue.put(("summary", (success, fail, total)))

    def _queue_error(self, msg):
        self.result_queue.put(("error", msg))

    def _queue_done(self):
        self.result_queue.put(("done", None))

    def _poll_queue(self):
        """定期检查结果队列，在主线程更新 UI"""
        try:
            while True:
                msg = self.result_queue.get_nowait()
                msg_type, data = msg

                if msg_type == "status":
                    self.status_var.set(data)

                elif msg_type == "progress":
                    self.progress_bar["value"] = data

                elif msg_type == "result":
                    self._insert_result_row(data)

                elif msg_type == "summary":
                    success, fail, total = data
                    self.summary_var.set(f"成功: {success}  |  失败: {fail}  |  总计: {total}")

                elif msg_type == "error":
                    messagebox.showwarning("提示", data)
                    self.status_var.set(data)

                elif msg_type == "done":
                    self.is_running = False
                    self.stop_requested = False
                    self.start_btn.config(state="normal", bg=BTN_BG)
                    self.stop_btn.config(state="disabled", bg="#C0C0C0")
                    self.browse_btn.config(state="normal")
                    self.progress_bar["value"] = self.progress_bar["maximum"]

        except queue.Empty:
            pass

        # 继续轮询
        self.root.after(100, self._poll_queue)

    def _insert_result_row(self, result):
        """在表格中插入一行结果"""
        order_id = result.get("order_id", "")
        act_count = result.get("act_count", 0)
        status = result.get("status", "")

        display_count = str(act_count) if status == "成功" else "-"

        tags = ()
        if status == "失败" or status == "未找到" or status == "超时":
            tags = ("error",)
        elif status == "已停止":
            tags = ("stopped",)

        self.tree.insert("", "end", values=(order_id, display_count, status), tags=tags)
        self.tree.yview_moveto(1)  # 滚动到底部

        # 设置标签样式
        self.tree.tag_configure("error", foreground=TEXT_ERROR)
        self.tree.tag_configure("stopped", foreground=TEXT_HINT)

    def _clear_results(self):
        """清空结果"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.results = []
        self.summary_var.set("")
        self.progress_bar["value"] = 0

    # ---- 复制功能 ----

    def _copy_all(self):
        """复制全部结果到剪贴板"""
        rows = []
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            rows.append("\t".join(str(v) for v in values))

        if not rows:
            messagebox.showinfo("提示", "没有可复制的结果")
            return

        text = "工单编号\tact_账户数\t状态\n" + "\n".join(rows)
        self._copy_to_clipboard(text)
        messagebox.showinfo("已复制", f"已复制 {len(rows)} 条结果到剪贴板")

    def _copy_selected(self):
        """复制选中的行"""
        selected = self.tree.selection()
        if not selected:
            return

        rows = []
        for item in selected:
            values = self.tree.item(item, "values")
            rows.append("\t".join(str(v) for v in values))

        text = "\n".join(rows)
        self._copy_to_clipboard(text)

    def _show_tree_menu(self, event):
        """右键菜单"""
        self.tree_menu.post(event.x_root, event.y_root)

    def _copy_to_clipboard(self, text):
        """复制文本到系统剪贴板"""
        if IS_MAC:
            try:
                import subprocess
                subprocess.run(["pbcopy"], input=text, text=True, timeout=3)
                return
            except:
                pass

        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except:
            pass

    # ==================== 生命周期 ====================

    def _on_close(self):
        self.stop_requested = True
        self.is_running = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# =========================== 入口 ===========================

def main():
    app = WorkorderActCounterApp()
    app.run()


if __name__ == "__main__":
    main()
