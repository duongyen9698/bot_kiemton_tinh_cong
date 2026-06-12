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
from sapo.fetch_orders import load_cookie

DEFAULT_RETURN_LIMIT = 1000
FALLBACK_MAX_PAGES = 20


def build_headers(settings: SapoSettings) -> dict[str, str]:
    base = settings.admin_base_url
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "vi-VN,vi;q=0.9,en;q=0.8,ru;q=0.7",
        "priority": "u=1, i",
        "referer": f"{base}/admin/order_returns",
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


def fetch_order_returns_page(
    settings: SapoSettings,
    *,
    created_on_min: str,
    created_on_max: str,
    page: int,
    limit: int,
    headers: dict[str, str],
) -> dict:
    params = {
        "sort": "created_on:desc",
        "page": str(page),
        "limit": str(limit),
        "created_on_min": created_on_min,
        "created_on_max": created_on_max,
    }
    base_url = f"{settings.admin_base_url}/admin/order_returns/search.json"
    url = f"{base_url}?{urlencode(params)}"
    request = Request(url=url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=120) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as e:
        if e.code in (401, 403):
            raise SapoAuthError(f"Order returns API HTTP {e.code}") from e
        raise
    return json.loads(payload)


def fetch_order_returns_json(
    settings: SapoSettings,
    *,
    start_date: date,
    end_date: date,
    limit: int = DEFAULT_RETURN_LIMIT,
    max_pages_fallback: int = FALLBACK_MAX_PAGES,
    headers: dict[str, str] | None = None,
) -> dict:
    created_on_min, created_on_max = build_utc_window_for_vn(start_date, end_date)
    if headers is None:
        headers = build_headers(settings)

    first_page_data = fetch_order_returns_page(
        settings,
        created_on_min=created_on_min,
        created_on_max=created_on_max,
        page=1,
        limit=limit,
        headers=headers,
    )
    first_page_returns = first_page_data.get("order_returns", [])
    total_pages = first_page_data.get("total_pages")
    max_pages = (
        int(total_pages)
        if isinstance(total_pages, int) and total_pages > 0
        else max_pages_fallback
    )

    all_returns: list[dict] = []
    seen_ids: set[int] = set()
    page_stats: list[dict] = []

    def add_returns(page: int, returns: list[dict]) -> int:
        added = 0
        for item in returns:
            item_id = item.get("id")
            if isinstance(item_id, int) and item_id in seen_ids:
                continue
            if isinstance(item_id, int):
                seen_ids.add(item_id)
            all_returns.append(item)
            added += 1
        page_stats.append({"page": page, "fetched": len(returns), "added": added})
        return added

    add_returns(1, first_page_returns)
    for page in range(2, max_pages + 1):
        data = fetch_order_returns_page(
            settings,
            created_on_min=created_on_min,
            created_on_max=created_on_max,
            page=page,
            limit=limit,
            headers=headers,
        )
        page_returns = data.get("order_returns", [])
        add_returns(page, page_returns)
        if not page_returns:
            break

    return {
        "meta": {
            "from_date": format_vn_date(start_date),
            "to_date": format_vn_date(end_date),
            "timezone": "Asia/Ho_Chi_Minh",
            "created_on_min": created_on_min,
            "created_on_max": created_on_max,
            "limit": limit,
            "detected_total_pages": total_pages,
            "max_pages_used": max_pages,
            "page_stats": page_stats,
            "total_fetched": len(all_returns),
            "pages_fetched": len(page_stats),
        },
        "order_returns": all_returns,
    }


def fetch_order_returns_today_json(settings: SapoSettings) -> dict:
    today = today_vn()
    return fetch_order_returns_json(settings, start_date=today, end_date=today)
