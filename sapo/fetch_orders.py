from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sapo.config import SapoSettings
from sapo.exc import SapoAuthError

VN_TZ = timezone(timedelta(hours=7))


def load_cookie(settings: SapoSettings) -> str:
    cookie = settings.cookie_file.read_text(encoding="utf-8").strip()
    if not cookie:
        raise ValueError("File cookie Sapo trống. Chạy đăng nhập hoặc cập nhật cookie.")
    return cookie


def build_today_utc_window_for_vn() -> tuple[str, str]:
    now_vn = datetime.now(VN_TZ)
    start_vn = datetime(now_vn.year, now_vn.month, now_vn.day, 0, 0, 0, tzinfo=VN_TZ)
    end_vn = start_vn + timedelta(days=1) - timedelta(milliseconds=1)
    start_utc = start_vn.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_utc = end_vn.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return start_utc, end_utc


def build_headers(settings: SapoSettings) -> dict[str, str]:
    base = settings.admin_base_url
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "vi-VN,vi;q=0.9,en;q=0.8,ru;q=0.7",
        "priority": "u=1, i",
        "referer": f"{base}/admin/orders?processed_on=today",
        "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
        ),
        "x-bizweb-accept-language": "vi",
        "x-bizweb-search-type": "partial",
        "x-sapo-client": "frontend",
        "cookie": load_cookie(settings),
    }


def fetch_orders_today_json(settings: SapoSettings) -> dict:
    processed_on_min, processed_on_max = build_today_utc_window_for_vn()
    params = {
        "processed_on": "today",
        "processed_on_min": processed_on_min,
        "processed_on_max": processed_on_max,
        "page": "1",
        "limit": "1000",
        "query": "",
    }
    base_url = f"{settings.admin_base_url}/admin/orders/search.json"
    url = f"{base_url}?{urlencode(params)}"
    request = Request(url=url, headers=build_headers(settings), method="GET")
    try:
        with urlopen(request, timeout=60) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as e:
        if e.code in (401, 403):
            raise SapoAuthError(f"Orders API HTTP {e.code}") from e
        raise
    return json.loads(payload)
