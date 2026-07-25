from __future__ import annotations

import re
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from sapo.config import SapoSettings


def default_oauth_login_url(settings: SapoSettings) -> str:
    """URL OAuth mặc định (clientId giữ từ portal Sapo gốc), thay shop theo SAPO_ADMIN_BASE_URL."""
    shop = settings.shop_domain_slug
    host = settings.admin_hostname
    return (
        "https://accounts.sapo.vn/login?"
        f"clientId=EzvRnnBPP8&domain={shop}&relativeContextPath=%252fadmin%252fdashboard&"
        "redirectUrl=https%3A%2F%2Faccounts.sapo.vn%2Foauth%2Fauthorize%3Fclient_id%3DEzvRnnBPP8%26"
        "redirect_uri%3Dhttps%253a%252f%252fapp.sapo.vn%252foauth%252fSapoSSOOauthCallback%26"
        "scope%3Dprofile%26response_type%3Dcode%26state%3D%257b%2522redirectUrl%2522%253a%2522"
        f"https%253a%252f%252f{host}%253a443%252fadmin%252fauthorization%252flogin"
        "%253freturnUrl%253d%25252fadmin%25252fdashboard%2522%257d&appSource=WEB"
    )


def _cookies_for_header(cookies: list[dict]) -> str:
    wanted: list[tuple[str, str]] = []
    for c in cookies:
        domain = (c.get("domain") or "").lower()
        if "mysapo.net" in domain or domain.endswith("sapo.vn"):
            wanted.append((c["name"], c["value"]))
    if not wanted:
        return ""
    priority = (
        "_admin_session_id",
        "bizweb-admin",
        "JSESSIONID",
        "storefront_digest",
        "_ab",
        "CloseBannerSurveyCount",
    )
    order_map = {n: i for i, n in enumerate(priority)}
    wanted.sort(key=lambda nv: (order_map.get(nv[0], 99), nv[0]))
    seen: set[str] = set()
    parts: list[str] = []
    for name, value in wanted:
        if name in seen:
            continue
        seen.add(name)
        parts.append(f"{name}={value}")
    return "; ".join(parts)


def _username_selector(page) -> str:
    """Sapo đổi #username → #phoneNumber (2026); giữ fallback form cũ."""
    if page.locator("#phoneNumber").count():
        return "#phoneNumber"
    return "#username"


def _fill_login_form(page, username: str, password: str, timeout_ms: int) -> None:
    page.set_default_timeout(timeout_ms)
    try:
        page.wait_for_load_state("networkidle", timeout=min(20_000, timeout_ms))
    except PlaywrightTimeoutError:
        pass

    user_sel = _username_selector(page)
    page.wait_for_selector(f"{user_sel}, #password", state="visible", timeout=timeout_ms)
    time.sleep(0.5)
    page.locator(user_sel).click()
    page.locator(user_sel).fill(username)
    page.locator("#password").click()
    page.locator("#password").fill(password)
    user_id = user_sel.lstrip("#")
    page.evaluate(
        """
        ([userId]) => {
            for (const id of [userId, 'password']) {
                const el = document.getElementById(id);
                if (!el) continue;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
            if (window.$) {
                $(`#${userId}`).trigger('input').trigger('keyup');
                $('#password').trigger('input').trigger('keyup');
            }
        }
        """,
        user_id,
    )
    time.sleep(0.4)


def _click_login_submit(page, timeout_ms: int) -> None:
    """Nút Đăng nhập — form React mới hoặc pos-login-form cũ (headless hay disabled)."""
    page.set_default_timeout(timeout_ms)
    submit = page.get_by_role("button", name="Đăng nhập")
    if submit.count():
        btn = submit.first
        if btn.is_disabled():
            btn.evaluate("b => { b.removeAttribute('disabled'); b.click(); }")
        else:
            btn.click()
        return

    page.evaluate(
        """
        const form = document.getElementById('pos-login-form');
        if (!form) throw new Error('Không tìm thấy nút Đăng nhập');
        const btn = form.querySelector(
            'button.btn-login[type="submit"]:not(#forgot-pass-submit):not(#typing-domain-submit)'
        );
        if (!btn) throw new Error('Không tìm thấy nút Đăng nhập');
        btn.style.minHeight = '48px';
        btn.removeAttribute('disabled');
        btn.click();
        """
    )


def login_and_save_cookies(
    settings: SapoSettings,
    *,
    headed: bool = False,
    timeout_ms: int = 120_000,
) -> None:
    login_url = settings.login_url_override or default_oauth_login_url(settings)
    cookie_path = settings.cookie_file
    cookie_path.parent.mkdir(parents=True, exist_ok=True)
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    failure_shot = settings.work_dir / "sapo_login_failure.png"

    host_escaped = re.escape(settings.admin_hostname)
    admin_re = re.compile(rf"https://{host_escaped}(?::\d+)?/admin", re.I)
    dashboard_url = f"{settings.admin_base_url}/admin/dashboard"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not headed,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        try:
            context = browser.new_context(
                locale="vi-VN",
                viewport={"width": 1280, "height": 960},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            page.goto(login_url, wait_until="domcontentloaded", timeout=timeout_ms)

            if page.get_by_text(re.compile(r"captcha", re.I)).count() > 0:
                raise RuntimeError("Trang có captcha — không thể đăng nhập tự động.")

            _fill_login_form(page, settings.username, settings.password, timeout_ms)
            _click_login_submit(page, timeout_ms)

            try:
                page.wait_for_url(admin_re, timeout=timeout_ms)
            except PlaywrightTimeoutError:
                page.wait_for_load_state("networkidle", timeout=min(60_000, timeout_ms))
                if not admin_re.search(page.url):
                    page.goto(
                        dashboard_url,
                        wait_until="domcontentloaded",
                        timeout=timeout_ms,
                    )

            cookies = context.cookies()
            header = _cookies_for_header(cookies)
            if not header or "bizweb-admin" not in header:
                page.screenshot(path=str(failure_shot), full_page=True)
                raise RuntimeError(
                    "Không lấy được cookie bizweb-admin (đăng nhập có thể thất bại). "
                    f"Đã chụp {failure_shot}. URL cuối: {page.url}"
                )

            cookie_path.write_text(header + "\n", encoding="utf-8")
        finally:
            browser.close()
