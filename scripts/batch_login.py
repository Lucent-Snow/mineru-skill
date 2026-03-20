#!/usr/bin/env python3
"""
MinerU 批量登录 - 全自动获取/续期 Token
使用 Playwright headless 浏览器自动化：
  - 自动填写账号密码
  - 自动点击阿里云验证码
  - 自动删除旧 Token、创建新 Token
  - 保存到 ~/.mineru/all_tokens.json

用法：
  python batch_login.py            # headless 模式（默认）
  python batch_login.py --headed   # 打开浏览器界面调试
"""
import json
import sys
import time
import random
import requests
import yaml
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _config import TOKENS_FILE, ACCOUNTS_FILE, API_BASE_URL, ensure_data_dir

from playwright.sync_api import sync_playwright

HEADED = "--headed" in sys.argv

# Stealth JS: 伪装浏览器特征，绕过 WebDriver 检测
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
delete navigator.__proto__.webdriver;
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const p = [
            {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
            {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
            {name: 'Native Client', filename: 'internal-nacl-plugin'},
        ];
        p.length = 3; return p;
    }
});
Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en-US', 'en']});
window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};
const origQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (p) => (
    p.name === 'notifications' ? Promise.resolve({state: Notification.permission}) : origQuery(p)
);
Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
const getParam = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(p) {
    if (p === 37445) return 'Intel Inc.';
    if (p === 37446) return 'Intel Iris OpenGL Engine';
    return getParam.call(this, p);
};
"""


def load_accounts():
    """加载账户配置"""
    if not ACCOUNTS_FILE.exists():
        print(f"账户配置文件不存在: {ACCOUNTS_FILE}")
        print("请从 assets/accounts.yaml.example 复制并编辑")
        sys.exit(1)
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["accounts"]


def save_all_tokens(tokens):
    """保存 Token 到文件"""
    ensure_data_dir()
    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2, ensure_ascii=False)


def type_human(page, selector, text):
    """模拟人工逐字输入"""
    page.locator(selector).click()
    time.sleep(random.uniform(0.3, 0.6))
    for char in text:
        page.keyboard.type(char)
        time.sleep(random.uniform(0.08, 0.18))
    time.sleep(random.uniform(0.4, 0.8))


def click_captcha(page):
    """点击阿里云验证码 checkbox"""
    for attempt in range(15):
        try:
            el = page.locator("#aliyunCaptcha-checkbox-icon")
            if el.is_visible(timeout=2000):
                el.click()
                print(f"    click captcha (attempt {attempt + 1})")
                time.sleep(3)
                if not page.locator(
                    "#aliyunCaptcha-window-popup.window-show"
                ).is_visible(timeout=3000):
                    print("    captcha passed")
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def login_account(account, browser, all_tokens):
    """登录单个账户，获取 Token"""
    email = account["email"]
    password = account["password"]
    name = account["name"]

    print(f"\n{'='*55}")
    print(f"  [{name}] {email}")
    print(f"{'='*55}")

    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    )
    page = context.new_page()
    page.add_init_script(STEALTH_JS)

    try:
        # 访问 Token 管理页面
        print("  [1/5] navigate...")
        page.goto("https://mineru.net/apiManage/token", wait_until="networkidle")
        time.sleep(2)

        # 点击登录按钮
        print("  [2/5] click login...")
        try:
            page.get_by_text("登录", exact=True).first.click(timeout=10000)
            time.sleep(3)
        except Exception:
            print("    login button not found")
            return False

        # 等待登录表单
        try:
            page.wait_for_selector(
                'input[placeholder="邮箱/手机号/用户名"]', timeout=10000
            )
        except Exception:
            print("    login form not found")
            return False

        # 填写账号密码
        print("  [3/5] input credentials...")
        type_human(page, 'input[placeholder="邮箱/手机号/用户名"]', email)
        time.sleep(0.5)
        type_human(page, 'input[type="password"]', password)
        time.sleep(1)

        # 提交
        print("  [4/5] submit...")
        page.locator("button.loginButton--wFHGh").click()
        time.sleep(4)

        # 处理验证码
        print("  [5/5] captcha...")
        click_captcha(page)

        # 等待登录成功
        print("  waiting for login (max 60s)...")
        for i in range(60):
            time.sleep(1)
            cookies = {
                c["name"]: c["value"]
                for c in context.cookies()
                if c["name"] in ["uaa-token", "opendatalab_session"]
            }

            if len(cookies) >= 2:
                print(f"  login OK ({i + 1}s)")
                uaa_token = cookies["uaa-token"]
                headers = {
                    "authorization": f"Bearer {uaa_token}",
                    "content-type": "application/json",
                }

                # 删除旧 Token
                r = requests.get(
                    f"{API_BASE_URL}/tokens", headers=headers, timeout=10
                )
                if r.status_code == 200:
                    token_list = r.json()["data"].get("list", [])
                    if token_list:
                        print(f"    delete {len(token_list)} old token(s)")
                        for tok in token_list:
                            requests.delete(
                                f"{API_BASE_URL}/tokens/{tok['id']}",
                                headers=headers,
                            )

                # 创建新 Token
                ts = datetime.now().strftime("%Y%m%d%H%M%S")
                token_name = f"token-{ts}"
                r = requests.post(
                    f"{API_BASE_URL}/tokens",
                    headers=headers,
                    json={"token_name": token_name},
                    timeout=10,
                )

                if r.status_code == 200:
                    result = r.json()["data"]
                    print(f"    new token: {token_name}")
                    all_tokens[email] = {
                        "name": name,
                        "token_name": token_name,
                        "token": result["token"],
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "expired_at": result["expired_at"],
                    }
                    return True
                else:
                    print(f"    token creation failed: {r.status_code}")
                    try:
                        print(f"    response: {r.text}")
                    except Exception:
                        pass
                    return False

            if (i + 1) % 15 == 0:
                click_captcha(page)
                print(f"    [{i + 1}s]...")

        print("  timeout")
        return False
    finally:
        context.close()


def main():
    mode = "headed" if HEADED else "headless"
    print(f"{'='*55}")
    print(f"  MinerU batch login ({mode})")
    print(f"{'='*55}")

    accounts = load_accounts()
    all_tokens = {}
    print(f"\n  {len(accounts)} account(s)\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not HEADED,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        success_count = 0
        for i, account in enumerate(accounts, 1):
            print(f"\n  [{i}/{len(accounts)}]")
            for attempt in range(2):
                if login_account(account, browser, all_tokens):
                    success_count += 1
                    save_all_tokens(all_tokens)
                    break
                elif attempt == 0:
                    print("    retrying...")
                    time.sleep(3)
            if i < len(accounts):
                time.sleep(2)

        browser.close()

    print(f"\n{'='*55}")
    print(f"  done: {success_count}/{len(accounts)}")
    print(f"  saved: {TOKENS_FILE}")
    print(f"{'='*55}")
    for email, info in all_tokens.items():
        print(f"  {info['name']} ({email})")
        print(f"    token: {info['token_name']}")
        print(f"    expires: {info['expired_at']}")


if __name__ == "__main__":
    main()
