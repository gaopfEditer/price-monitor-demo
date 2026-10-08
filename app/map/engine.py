from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MapEvaluation:
    violation: bool
    filtered_trap: bool
    trap_reason: str
    compare_price: float
    reason: dict


def is_authorized_seller(seller: str, whitelist: dict[str, list[str]]) -> bool:
    s = seller.strip().lower()
    for names in whitelist.values():
        if any(alias.lower() == s for alias in names):
            return True
    return False


def evaluate_map(
    *,
    condition: str,
    is_bundle: bool,
    list_price: float,
    shipping: float,
    map_price: float,
    use_landed: bool,
    streak_below: int,
    required_streak: int = 2,
) -> MapEvaluation:
    if condition != "new":
        return MapEvaluation(False, True, "used/refurbished excluded", list_price, {"trap": "condition"})
    if is_bundle:
        return MapEvaluation(False, True, "bundle listing excluded", list_price, {"trap": "bundle"})

    compare = list_price + shipping if use_landed else list_price
    # Shipping trap: list price dips below MAP but landed cost does not (list-price MAP mode).
    if not use_landed and list_price < map_price and (list_price + shipping) >= map_price:
        return MapEvaluation(
            False,
            True,
            "list below MAP but landed price meets MAP (shipping trap)",
            compare,
            {"trap": "shipping_inclusive", "list": list_price, "landed": list_price + shipping},
        )

    if compare >= map_price:
        return MapEvaluation(False, False, "", compare, {"ok": True})

    if streak_below < required_streak:
        return MapEvaluation(
            False,
            False,
            "",
            compare,
            {"pending_confirm": True, "streak": streak_below, "required": required_streak},
        )

    return MapEvaluation(
        True,
        False,
        "",
        compare,
        {"violation": True, "map": map_price, "observed": compare, "streak": streak_below},
    )
