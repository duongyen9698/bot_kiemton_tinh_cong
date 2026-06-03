from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


def to_float(value: object) -> float:
    if value is None:
        return float("inf")
    return float(value)


def reconcile_to_csv(
    orders: dict,
    products_payload: dict,
    output_csv: Path,
) -> tuple[int, int]:
    """
    Gộp đơn hôm nay với catalog variant theo SKU; ghi CSV.
    Returns (matched_count, unmatched_count).
    """
    orders_list = orders.get("orders", [])
    products = products_payload.get("products", [])

    sku_to_variant: dict[str, dict] = {}
    for product in products:
        product_name = product.get("name") or "(khong co ten)"
        for variant in product.get("variants") or []:
            sku = variant.get("sku")
            if sku:
                sku_to_variant[sku] = {
                    "product_name": product_name,
                    "unit": variant.get("unit") or "",
                    "inventory_quantity": variant.get("inventory_quantity"),
                    "variant_title": variant.get("title") or "",
                }

    sold_by_sku: dict[str, float] = defaultdict(float)
    sold_name_by_sku: dict[str, str] = {}
    for order in orders_list:
        for line_item in order.get("line_items") or []:
            sku = line_item.get("sku")
            qty = float(line_item.get("quantity") or 0)
            if not sku:
                continue
            sold_by_sku[sku] += qty
            if sku not in sold_name_by_sku:
                sold_name_by_sku[sku] = (
                    line_item.get("name")
                    or line_item.get("title")
                    or "(khong co ten tren don)"
                )

    matched_rows: list[dict] = []
    unmatched_rows: list[dict] = []
    for sku, sold_qty in sorted(sold_by_sku.items(), key=lambda x: x[0]):
        variant = sku_to_variant.get(sku)
        if variant is None:
            unmatched_rows.append(
                {
                    "sku": sku,
                    "sold_name": sold_name_by_sku.get(sku, ""),
                    "sold_qty": sold_qty,
                }
            )
            continue
        matched_rows.append(
            {
                "sku": sku,
                "product_name": variant["product_name"],
                "unit": variant["unit"],
                "inventory_quantity": variant["inventory_quantity"],
                "sold_qty": sold_qty,
            }
        )

    matched_rows.sort(
        key=lambda r: (to_float(r["inventory_quantity"]), r["product_name"], r["sku"])
    )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "ten_san_pham",
                "sku",
                "don_vi",
                "so_luong_da_ban_hom_nay",
                "ton_kho_con_lai",
                "trang_thai_map",
            ]
        )
        for row in matched_rows:
            writer.writerow(
                [
                    row["product_name"],
                    row["sku"],
                    row["unit"],
                    row["sold_qty"],
                    row["inventory_quantity"],
                    "matched",
                ]
            )
        for row in unmatched_rows:
            writer.writerow(
                [
                    row["sold_name"],
                    row["sku"],
                    "",
                    row["sold_qty"],
                    "",
                    "unmatched",
                ]
            )

    return len(matched_rows), len(unmatched_rows)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)
