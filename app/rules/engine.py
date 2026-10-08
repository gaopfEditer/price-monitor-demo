from __future__ import annotations

import re


def is_clearance_price(price: float) -> bool:
    """Domain rule from A11: prices ending in .x1 often indicate clearance."""
    cents = int(round(price * 100)) % 100
    return cents % 10 == 1


def suggested_price(competitor_min: float, discount_pct: float, floor: float) -> float:
    val = competitor_min * (1 - discount_pct / 100.0)
    return round(max(val, floor), 2)


CLEARANCE_RE = re.compile(r"\.(\d)1\b")
