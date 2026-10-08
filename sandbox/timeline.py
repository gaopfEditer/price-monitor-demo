"""14-day scripted price/stock events for demo narrative."""
from __future__ import annotations

import json
from pathlib import Path

# Key demo SKUs (indices in catalog)
DEMO = {
    "jitter": "SKU-001",
    "real_drop": "SKU-002",
    "flash_sale": "SKU-003",
    "pack_trap": "SKU-004",  # single unit listing vs 2-pack elsewhere
    "map_violation": "SKU-005",
    "map_used_trap": "SKU-006",
    "map_shipping_trap": "SKU-007",
    "oos_restock": "SKU-008",
    "delist_relist": "SKU-009",
    "clearance_ends_in_1": "SKU-010",
}


def build_timeline() -> dict:
    """Day-indexed events applied on each /admin/tick."""
    days: list[dict] = []
    for d in range(1, 15):
        changes: list[dict] = []
        promos: list[dict] = []
        flags: list[dict] = []

        if d == 1:
            changes.append({"target": "shop-a", "sku": DEMO["jitter"], "mode": "jitter_cents", "cents": 2})
        if d == 2:
            changes.append({"target": "shop-a", "sku": DEMO["jitter"], "mode": "jitter_cents", "cents": -2})
        if d == 3:
            changes.append(
                {
                    "target": "shop-a",
                    "sku": DEMO["real_drop"],
                    "mode": "set_price",
                    "price": 349.99,
                    "was": 429.99,
                }
            )
        if d == 4:
            promos.append({"target": "shop-b", "sku": DEMO["flash_sale"], "mode": "flash", "hours": 24, "discount_pct": 15})
        if d == 5:
            promos.append({"target": "shop-b", "sku": DEMO["flash_sale"], "mode": "flash_end"})
        if d == 6:
            flags.append({"target": "shop-c", "mode": "challenge_burst", "count": 3})
        if d == 7:
            changes.append({"target": "market-x", "sku": DEMO["map_violation"], "mode": "map_breach", "seller": "Unauthorized Outlet 7"})
        if d == 8:
            changes.append(
                {
                    "target": "market-x",
                    "sku": DEMO["map_used_trap"],
                    "mode": "used_listing",
                    "price": 199.99,
                    "seller": "SecondCup Resale",
                }
            )
        if d == 9:
            changes.append(
                {
                    "target": "market-x",
                    "sku": DEMO["map_shipping_trap"],
                    "mode": "low_listing_high_shipping",
                    "price": 399.0,
                    "shipping": 89.0,
                    "seller": "Budget Beans LLC",
                }
            )
        if d == 10:
            changes.append({"target": "shop-d", "sku": DEMO["oos_restock"], "mode": "out_of_stock"})
        if d == 11:
            changes.append({"target": "shop-d", "sku": DEMO["oos_restock"], "mode": "in_stock"})
        if d == 12:
            changes.append({"target": "shop-a", "sku": DEMO["delist_relist"], "mode": "delisted"})
        if d == 13:
            changes.append({"target": "shop-a", "sku": DEMO["delist_relist"], "mode": "relisted"})
        if d == 14:
            changes.append({"target": "shop-a", "sku": DEMO["clearance_ends_in_1"], "mode": "clearance_price", "price": 129.91})

        # shop-d DOM revision every 4 days
        if d % 4 == 0:
            flags.append({"target": "shop-d", "mode": "dom_revision", "version": d // 4})

        days.append({"day": d, "changes": changes, "promos": promos, "flags": flags})
    return {"days": days, "demo_skus": DEMO}


def save_timeline(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_timeline(), indent=2))


def load_timeline(path: Path) -> dict:
    if not path.exists():
        save_timeline(path)
    return json.loads(path.read_text())
