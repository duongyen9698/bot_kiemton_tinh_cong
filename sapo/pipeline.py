from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

from sapo.config import PROJECT_ROOT, load_settings
from sapo.fetch_orders import fetch_orders_today_json
from sapo.fetch_products import fetch_all_products
from sapo.reconcile import reconcile_to_csv
from sapo.session import with_sapo_auth


def run_reconciliation_today(
    *,
    headed: bool = False,
    timeout_ms: int = 120_000,
) -> Path:
    """
    Đăng nhập (nếu cần), tải đơn + sản phẩm trong ngày (VN), đối soát, trả về đường dẫn CSV.
    """
    load_dotenv(PROJECT_ROOT / ".env")
    settings = load_settings()
    settings.work_dir.mkdir(parents=True, exist_ok=True)

    orders_path = settings.work_dir / "orders_today_limit_5000.json"
    products_path = settings.work_dir / "products_all_pages_limit_250.json"
    output_csv = settings.work_dir / "inventory_reconciliation_today.csv"

    def fetch_and_save() -> None:
        orders = fetch_orders_today_json(settings)
        orders_path.write_text(
            json.dumps(orders, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Đã ghi {orders_path}")

        products = fetch_all_products(settings)
        products_path.write_text(
            json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Đã ghi {products_path}")

    with_sapo_auth(
        settings,
        fetch_and_save,
        headed=headed,
        timeout_ms=timeout_ms,
    )

    orders_data = json.loads(orders_path.read_text(encoding="utf-8"))
    products_data = json.loads(products_path.read_text(encoding="utf-8"))
    matched, unmatched = reconcile_to_csv(orders_data, products_data, output_csv)
    print(f"Đã ghi {output_csv}")
    print(f"Matched rows: {matched}")
    print(f"Unmatched rows: {unmatched}")

    return output_csv
