from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sapo.config import SapoSettings
from sapo.exc import SapoAuthError
from sapo.fetch_orders import load_cookie

DEFAULT_LIMIT = 250
FALLBACK_MAX_PAGES = 20


def build_headers(settings: SapoSettings) -> dict[str, str]:
    base = settings.admin_base_url
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "vi-VN,vi;q=0.9,en;q=0.8,ru;q=0.7",
        "cookie": load_cookie(settings),
        "priority": "u=1, i",
        "referer": f"{base}/admin/products",
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
        "x-sapo-client": "frontend",
    }


def fetch_products_page(
    settings: SapoSettings, page: int, limit: int, headers: dict[str, str]
) -> dict:
    params = {
        "query": "",
        "page": str(page),
        "limit": str(limit),
    }
    base_url = f"{settings.admin_base_url}/admin/products.json"
    url = f"{base_url}?{urlencode(params)}"
    request = Request(url=url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=120) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as e:
        if e.code in (401, 403):
            raise SapoAuthError(f"Products API HTTP {e.code}") from e
        raise
    return json.loads(payload)


def fetch_all_products(
    settings: SapoSettings,
    *,
    limit: int = DEFAULT_LIMIT,
    max_pages_fallback: int = FALLBACK_MAX_PAGES,
    headers: dict[str, str] | None = None,
) -> dict:
    if headers is None:
        headers = build_headers(settings)
    first_page_data = fetch_products_page(settings, 1, limit, headers)
    first_page_products = first_page_data.get("products", [])
    total_pages = first_page_data.get("total_pages")
    max_pages = (
        int(total_pages)
        if isinstance(total_pages, int) and total_pages > 0
        else max_pages_fallback
    )
    all_products: list[dict] = []
    seen_ids: set[int] = set()
    page_stats: list[dict] = []

    def add_products(page: int, products: list[dict]) -> int:
        added = 0
        for product in products:
            product_id = product.get("id")
            if isinstance(product_id, int) and product_id in seen_ids:
                continue
            if isinstance(product_id, int):
                seen_ids.add(product_id)
            all_products.append(product)
            added += 1
        page_stats.append({"page": page, "fetched": len(products), "added": added})
        return added

    add_products(1, first_page_products)
    for page in range(2, max_pages + 1):
        data = fetch_products_page(settings, page, limit, headers)
        page_products = data.get("products", [])
        add_products(page, page_products)
        if not page_products:
            break

    return {
        "meta": {
            "limit": limit,
            "detected_total_pages": total_pages,
            "max_pages_used": max_pages,
            "page_stats": page_stats,
            "unique_products": len(all_products),
        },
        "products": all_products,
    }
