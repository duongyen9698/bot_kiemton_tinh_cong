from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


def _normalize_unit(unit: object) -> str:
    return str(unit or "").strip()


def _order_sold_at(order: dict) -> str:
    """Thời điểm bán trên order (ISO UTC), dùng processed_on."""
    return str(order.get("processed_on") or order.get("created_on") or "")


def reconcile_to_csv(
    orders: dict,
    products_payload: dict,
    output_csv: Path,
) -> tuple[int, int]:
    """
    Gộp đơn hôm nay với catalog variant theo variant_id; ghi CSV.
    Đơn vị bán lấy từ line_item trên hóa đơn; tồn kho lấy từ variant tương ứng.
    Sắp xếp theo lần bán muộn nhất trong ngày (last_sold_at từ order.processed_on).
    Returns (matched_count, unmatched_count).
    """
    orders_list = orders.get("orders", [])
    products = products_payload.get("products", [])

    variant_id_to_variant: dict[int, dict] = {}
    for product in products:
        product_name = product.get("name") or "(khong co ten)"
        for variant in product.get("variants") or []:
            variant_id = variant.get("id")
            if not isinstance(variant_id, int):
                continue
            variant_id_to_variant[variant_id] = {
                "product_name": product_name,
                "unit": _normalize_unit(variant.get("unit")),
                "inventory_quantity": variant.get("inventory_quantity"),
                "variant_title": variant.get("title") or "",
                "variant_id": variant_id,
            }

    sold: dict[int, dict] = defaultdict(
        lambda: {
            "sold_qty": 0.0,
            "sold_unit": "",
            "sold_name": "",
            "variant_id": None,
            "last_sold_at": "",
        }
    )
    for order in orders_list:
        sold_at = _order_sold_at(order)
        for line_item in order.get("line_items") or []:
            variant_id = line_item.get("variant_id")
            if not isinstance(variant_id, int):
                continue
            qty = float(line_item.get("quantity") or 0)
            bucket = sold[variant_id]
            bucket["sold_qty"] += qty
            bucket["variant_id"] = variant_id
            if sold_at and sold_at > bucket["last_sold_at"]:
                bucket["last_sold_at"] = sold_at
            if not bucket["sold_unit"]:
                bucket["sold_unit"] = _normalize_unit(line_item.get("unit"))
            if not bucket["sold_name"]:
                bucket["sold_name"] = (
                    line_item.get("name")
                    or line_item.get("title")
                    or "(khong co ten tren don)"
                )

    matched_rows: list[dict] = []
    unmatched_rows: list[dict] = []
    for variant_id in sorted(sold):
        row = sold[variant_id]
        variant = variant_id_to_variant.get(variant_id)
        if variant is None:
            unmatched_rows.append(
                {
                    "variant_id": variant_id,
                    "sold_name": row["sold_name"],
                    "sold_qty": row["sold_qty"],
                    "sold_unit": row["sold_unit"],
                    "last_sold_at": row["last_sold_at"],
                }
            )
            continue
        sold_unit = row["sold_unit"] or variant["unit"]
        matched_rows.append(
            {
                "variant_id": variant_id,
                "product_name": variant["product_name"],
                "sold_unit": sold_unit,
                "inventory_unit": variant["unit"],
                "inventory_quantity": variant["inventory_quantity"],
                "sold_qty": row["sold_qty"],
                "last_sold_at": row["last_sold_at"],
            }
        )

    sort_key = lambda r: (
        r["last_sold_at"],
        str(r.get("variant_id") or ""),
        r.get("product_name") or r.get("sold_name") or "",
    )
    matched_rows.sort(key=sort_key)
    unmatched_rows.sort(key=sort_key)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "ten_san_pham",
                "ton_kho_con_lai",
                "don_vi",
                "so_luong_da_ban_hom_nay",
                "variant_id",
            ]
        )
        for row in matched_rows:
            writer.writerow(
                [
                    row["product_name"],
                    row["inventory_quantity"],
                    row["sold_unit"],
                    row["sold_qty"],
                    row["variant_id"],
                ]
            )
        for row in unmatched_rows:
            writer.writerow(
                [
                    row["sold_name"],
                    "",
                    row["sold_unit"],
                    row["sold_qty"],
                    row["variant_id"],
                ]
            )

    return len(matched_rows), len(unmatched_rows)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)
