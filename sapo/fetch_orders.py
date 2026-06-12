from __future__ import annotations

import json
from datetime import date
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sapo.config import SapoSettings
from sapo.dates import (
    build_utc_window_for_vn,
    format_vn_date,
    today_vn,
)
from sapo.exc import SapoAuthError

# Sapo cap ~250 đơn/request dù gửi limit cao hơn.
DEFAULT_ORDER_PAGE_LIMIT = 250
# Tối đa ~5000 đơn/tháng → 20 trang × 250.
FALLBACK_MAX_PAGES = 20


def load_cookie(settings: SapoSettings) -> str:
    cookie = settings.cookie_file.read_text(encoding="utf-8").strip()
    if not cookie:
        raise ValueError("File cookie Sapo trống. Chạy đăng nhập hoặc cập nhật cookie.")
    return cookie


def build_headers(
    settings: SapoSettings,
    *,
    referer_suffix: str = "orders?processed_on=today",
) -> dict[str, str]:
    base = settings.admin_base_url
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "vi-VN,vi;q=0.9,en;q=0.8,ru;q=0.7",
        "priority": "u=1, i",
        "referer": f"{base}/admin/{referer_suffix}",
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


def fetch_orders_page(
    settings: SapoSettings,
    *,
    processed_on_min: str,
    processed_on_max: str,
    page: int,
    limit: int,
    headers: dict[str, str],
    processed_on: str | None = None,
) -> dict:
    params: dict[str, str] = {
        "processed_on_min": processed_on_min,
        "processed_on_max": processed_on_max,
        "page": str(page),
        "limit": str(limit),
        "query": "",
    }
    if processed_on is not None:
        params["processed_on"] = processed_on
    base_url = f"{settings.admin_base_url}/admin/orders/search.json"
    url = f"{base_url}?{urlencode(params)}"
    request = Request(url=url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=120) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as e:
        if e.code in (401, 403):
            raise SapoAuthError(f"Orders API HTTP {e.code}") from e
        raise
    return json.loads(payload)


def fetch_orders_json(
    settings: SapoSettings,
    *,
    start_date: date,
    end_date: date,
    limit: int = DEFAULT_ORDER_PAGE_LIMIT,
    max_pages_fallback: int = FALLBACK_MAX_PAGES,
    headers: dict[str, str] | None = None,
) -> dict:
    """
    Lấy toàn bộ hóa đơn trong khoảng ngày VN.

    Gọi Sapo nhiều trang nội bộ; response trả một lần gồm ``meta`` + ``orders``.
    """
    processed_on_min, processed_on_max = build_utc_window_for_vn(start_date, end_date)
    if headers is None:
        headers = build_headers(settings, referer_suffix="orders")

    is_today = start_date == end_date == today_vn()
    processed_on = "today" if is_today else None

    first_page_data = fetch_orders_page(
        settings,
        processed_on_min=processed_on_min,
        processed_on_max=processed_on_max,
        page=1,
        limit=limit,
        headers=headers,
        processed_on=processed_on,
    )
    first_page_orders = first_page_data.get("orders", [])
    total_pages = first_page_data.get("total_pages")
    max_pages = (
        int(total_pages)
        if isinstance(total_pages, int) and total_pages > 0
        else max_pages_fallback
    )

    all_orders: list[dict] = []
    seen_ids: set[int] = set()
    page_stats: list[dict] = []

    def add_orders(page: int, orders: list[dict]) -> int:
        added = 0
        for order in orders:
            order_id = order.get("id")
            if isinstance(order_id, int) and order_id in seen_ids:
                continue
            if isinstance(order_id, int):
                seen_ids.add(order_id)
            all_orders.append(order)
            added += 1
        page_stats.append({"page": page, "fetched": len(orders), "added": added})
        return added

    add_orders(1, first_page_orders)
    for page in range(2, max_pages + 1):
        data = fetch_orders_page(
            settings,
            processed_on_min=processed_on_min,
            processed_on_max=processed_on_max,
            page=page,
            limit=limit,
            headers=headers,
            processed_on=processed_on,
        )
        page_orders = data.get("orders", [])
        add_orders(page, page_orders)
        if not page_orders or len(page_orders) < limit:
            break

    return {
        "meta": {
            "from_date": format_vn_date(start_date),
            "to_date": format_vn_date(end_date),
            "timezone": "Asia/Ho_Chi_Minh",
            "processed_on_min": processed_on_min,
            "processed_on_max": processed_on_max,
            "limit": limit,
            "detected_total_pages": total_pages,
            "max_pages_used": max_pages,
            "page_stats": page_stats,
            "total_fetched": len(all_orders),
            "pages_fetched": len(page_stats),
        },
        "orders": all_orders,
    }


def fetch_orders_today_json(settings: SapoSettings) -> dict:
    today = today_vn()
    return fetch_orders_json(settings, start_date=today, end_date=today)
