from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


def to_float(value: object) -> float:
    if value is None:
        return float("inf")
    return float(value)


def _normalize_unit(unit: object) -> str:
    return str(unit or "").strip()


def reconcile_to_csv(
    orders: dict,
    products_payload: dict,
    output_csv: Path,
) -> tuple[int, int]:
    """
    Gộp đơn hôm nay với catalog variant theo variant_id (fallback SKU); ghi CSV.
    Đơn vị bán lấy từ line_item trên hóa đơn; tồn kho lấy từ variant tương ứng.
    Returns (matched_count, unmatched_count).
    """
    orders_list = orders.get("orders", [])
    products = products_payload.get("products", [])

    variant_id_to_variant: dict[int, dict] = {}
    sku_to_variant: dict[str, dict] = {}
    for product in products:
        product_name = product.get("name") or "(khong co ten)"
        for variant in product.get("variants") or []:
            variant_id = variant.get("id")
            sku = variant.get("sku")
            info = {
                "product_name": product_name,
                "unit": _normalize_unit(variant.get("unit")),
                "inventory_quantity": variant.get("inventory_quantity"),
                "variant_title": variant.get("title") or "",
                "sku": sku or "",
                "variant_id": variant_id,
            }
            if isinstance(variant_id, int):
                variant_id_to_variant[variant_id] = info
            if sku:
                sku_to_variant[sku] = info

    SoldKey = int | str
    sold: dict[SoldKey, dict] = defaultdict(
        lambda: {
            "sold_qty": 0.0,
            "sold_unit": "",
            "sku": "",
            "sold_name": "",
            "variant_id": None,
        }
    )
    for order in orders_list:
        for line_item in order.get("line_items") or []:
            sku = line_item.get("sku")
            qty = float(line_item.get("quantity") or 0)
            if not sku:
                continue
            variant_id = line_item.get("variant_id")
            key: SoldKey = variant_id if isinstance(variant_id, int) else f"sku:{sku}"
            bucket = sold[key]
            bucket["sold_qty"] += qty
            bucket["sku"] = sku
            bucket["variant_id"] = variant_id
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
    for key in sorted(sold, key=lambda k: (isinstance(k, str), k)):
        row = sold[key]
        variant = None
        variant_id = row["variant_id"]
        if isinstance(variant_id, int):
            variant = variant_id_to_variant.get(variant_id)
        if variant is None and row["sku"]:
            variant = sku_to_variant.get(row["sku"])
        if variant is None:
            unmatched_rows.append(
                {
                    "sku": row["sku"],
                    "sold_name": row["sold_name"],
                    "sold_qty": row["sold_qty"],
                    "sold_unit": row["sold_unit"],
                }
            )
            continue
        sold_unit = row["sold_unit"] or variant["unit"]
        matched_rows.append(
            {
                "sku": row["sku"] or variant["sku"],
                "product_name": variant["product_name"],
                "sold_unit": sold_unit,
                "inventory_unit": variant["unit"],
                "inventory_quantity": variant["inventory_quantity"],
                "sold_qty": row["sold_qty"],
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
            ]
        )
        for row in matched_rows:
            writer.writerow(
                [
                    row["product_name"],
                    row["sku"],
                    row["sold_unit"],
                    row["sold_qty"],
                    row["inventory_quantity"],
                ]
            )
        for row in unmatched_rows:
            writer.writerow(
                [
                    row["sold_name"],
                    row["sku"],
                    row["sold_unit"],
                    row["sold_qty"],
                    "",
                ]
            )

    return len(matched_rows), len(unmatched_rows)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)
