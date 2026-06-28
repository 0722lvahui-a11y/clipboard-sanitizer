#!/usr/bin/env python3
"""
工单 act_ 查询脚本（桌面可见版）
- 用你本机已登录的 Chrome，打开 medialhub
- 逐个工单编号查询 → 点进详情 → 数 act_ → 输出结果
运行: python query_workorder_act.py
"""

import time, re, sys, os

# =========================== 配置 ===========================

# 要查询的工单编号列表（一行一个）
WORK_ORDERS = [
    # 把工单编号填在这里，例如:
    # "WD32026061909135121387667517",
    # "WD32026061818575170767591018",
]

# medialhub 工单列表页
WORKORDER_URL = "https://mediahub.meetsocial.cn/account/workOrder?_workOrderStatusList%5B0%5D=102"

# =========================== 初始化 Playwright ===========================

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("需要安装 playwright: pip install playwright")
    print("然后: playwright install chromium")
    sys.exit(1)

def find_chrome():
    """找系统 Chrome 路径"""
    paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ]
    for p in paths:
        if os.path.isfile(p):
            return p
    return None

def main():
    if not WORK_ORDERS or WORK_ORDERS == []:
        print("请先在脚本顶部的 WORK_ORDERS 列表里填入工单编号")
        return

    chrome_path = find_chrome()
    if not chrome_path:
        print("未找到 Chrome，请安装 Google Chrome")
        return

    print(f"使用浏览器: {chrome_path}")
    print(f"共 {len(WORK_ORDERS)} 个工单待查询\n")

    results = []

    with sync_playwright() as p:
        # 启动可见浏览器（非 headless，你能看到整个过程）
        browser = p.chromium.launch(
            headless=False,           # 可见！
            executable_path=chrome_path,
        )
        context = browser.new_context(
            viewport={"width": 1400, "height": 900},
            locale="zh-CN",
            # 不隔离存储——如果你Chrome已登录，可能共享session
        )
        page = context.new_page()

        # 先打开页面
        print("正在打开 medialhub...")
        page.goto(WORKORDER_URL, timeout=30000)
        page.wait_for_timeout(3000)

        # 检查是否登录
        current_url = page.url
        if "login" in current_url.lower() or "signin" in current_url.lower():
            print("\n⚠️  检测到登录页面！")
            print("请在浏览器中手动登录，登录完成后回到这里按 Enter 继续...")
            input()
            page.goto(WORKORDER_URL, timeout=30000)
            page.wait_for_timeout(2000)

        # 逐个工单查询
        for idx, order_id in enumerate(WORK_ORDERS):
            print(f"\n{'─'*50}")
            print(f"[{idx+1}/{len(WORK_ORDERS)}] {order_id}")
            print(f"{'─'*50}")

            try:
                # ==== 步骤1: 回列表页 ====
                page.goto(WORKORDER_URL, timeout=20000)
                page.wait_for_timeout(2000)

                # ==== 步骤2: 找到搜索框，输入工单编号 ====
                # 多种可能的搜索框选择器
                search_input = None
                for sel in [
                    'input[placeholder*="工单"]',
                    'input[placeholder*="编号"]',
                    'input[placeholder*="搜索"]',
                    'input[placeholder*="search"]',
                    'input[name*="order"]',
                    'input[name*="ticket"]',
                    'input[name*="workOrder"]',
                    'input[name*="search"]',
                    '.el-input__inner[placeholder*="工单"]',
                    '.ant-input[placeholder*="工单"]',
                ]:
                    try:
                        el = page.locator(sel).first
                        if el.count() > 0:
                            search_input = el
                            print(f"  找到搜索框: {sel}")
                            break
                    except:
                        continue

                if not search_input:
                    print("  ⚠️  未找到搜索框，尝试键盘输入...")
                    page.keyboard.press("Control+a")
                    page.keyboard.press("Backspace")
                    page.keyboard.type(order_id, delay=50)
                else:
                    search_input.click()
                    search_input.fill("")
                    search_input.type(order_id, delay=50)
                    page.wait_for_timeout(500)

                # ==== 步骤3: 点查询 ====
                page.keyboard.press("Enter")
                page.wait_for_timeout(2000)

                # 等结果加载
                page.wait_for_timeout(1500)

                # ==== 步骤4: 点工单编号进详情 ====
                clicked = False
                # 直接点页面上的工单编号文字
                for sel in [
                    f'text={order_id}',
                    f'a:has-text("{order_id}")',
                    f'[class*="link"]:has-text("{order_id}")',
                    f'tr:has-text("{order_id}")',
                ]:
                    try:
                        el = page.locator(sel).first
                        if el.count() > 0:
                            el.click()
                            clicked = True
                            print(f"  点击工单: {sel}")
                            break
                    except:
                        continue

                if not clicked:
                    print(f"  ⚠️  未找到工单链接，可能查询无结果")
                    results.append((order_id, "未找到", ""))
                    continue

                page.wait_for_timeout(3000)

                # ==== 步骤5: 在详情页找 act_ 账户 ====
                page_text = ""
                try:
                    page_text = page.inner_text("body")
                except:
                    page_text = ""

                # 正则匹配 act_ 开头的账户
                act_matches = re.findall(r'act_[a-zA-Z0-9_]+', page_text)
                unique_acts = list(set(act_matches))
                count = len(unique_acts)

                if count > 0:
                    print(f"  ✅ 找到 {count} 个 act_ 账户:")
                    for a in sorted(unique_acts):
                        print(f"     - {a}")
                else:
                    print(f"  ⚠️  未找到 act_ 账户")

                results.append((order_id, str(count), ", ".join(sorted(unique_acts))))

                # 短暂停顿
                time.sleep(0.5)

            except Exception as e:
                print(f"  ❌ 出错: {e}")
                results.append((order_id, "错误", str(e)[:100]))

        browser.close()

    # ==== 输出结果 ====
    print(f"\n\n{'='*60}")
    print(f"查询结果汇总")
    print(f"{'='*60}")
    print(f"{'工单编号':<35} {'act_数':<8} {'账户列表'}")
    print(f"{'─'*35} {'─'*8} {'─'*30}")

    for order_id, count, acts in results:
        print(f"{order_id:<35} {count:<8} {acts}")

    # 同时复制到剪贴板
    copy_text = "工单编号\tact_账户数\t账户列表\n"
    for order_id, count, acts in results:
        copy_text += f"{order_id}\t{count}\t{acts}\n"

    try:
        import subprocess
        subprocess.run(["pbcopy"], input=copy_text, text=True)
        print(f"\n📋 结果已复制到剪贴板")
    except:
        print(f"\n(Tab分隔格式，可直接粘贴到Excel)")
        print(copy_text)


if __name__ == "__main__":
    main()
