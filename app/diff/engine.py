from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class DiffDecision:
    emit: bool
    suppressed: bool
    event_type: str
    reason: dict


def _pct_change(old: float, new: float) -> float:
    if old == 0:
        return 100.0
    return abs((new - old) / old) * 100.0


def is_significant_change(
    old: float,
    new: float,
    abs_min: float = 1.0,
    pct_min: float = 3.0,
) -> bool:
    delta = abs(new - old)
    if delta < 0.001:
        return False
    if delta >= abs_min:
        return True
    return _pct_change(old, new) >= pct_min


def evaluate_price_change(
    history: list[tuple[datetime, float, str, float]],
    *,
    abs_min: float = 1.0,
    pct_min: float = 3.0,
    confirm_streak: int = 2,
    cooldown_hours: int = 6,
    last_event_at: Optional[datetime] = None,
) -> DiffDecision:
    """history: newest last; each row (ts, price, page_state, parse_confidence)."""
    usable = [h for h in history if h[2] == "ok" and h[3] >= 0.7 and h[1] is not None]
    if len(usable) < 2:
        return DiffDecision(False, True, "price_noise", {"why": "insufficient usable observations"})

    curr_ts, curr_p, _, _ = usable[-1]
    prev_ts, prev_p, _, _ = usable[-2]
    direction = "drop" if curr_p < prev_p else "rise" if curr_p > prev_p else "flat"

    # 24h flash sale: revert within ~36h suppresses alert
    if len(usable) >= 3:
        p3 = usable[-3][1]
        hours = (curr_ts - prev_ts).total_seconds() / 3600.0
        if direction == "rise" and hours <= 36 and p3 > prev_p and curr_p >= p3 * 0.98:
            return DiffDecision(
                False,
                True,
                "flash_sale",
                {"why": "24h flash promo reverted", "prev": prev_p, "curr": curr_p, "baseline": p3},
            )

    # Trailing equal observations at the new price (confirmation), compared to pre-change reference
    trail = 1
    for i in range(len(usable) - 2, -1, -1):
        if usable[i][1] == curr_p:
            trail += 1
        else:
            break
    reference_p = usable[-trail - 1][1] if len(usable) > trail else None
    if reference_p is None or not is_significant_change(reference_p, curr_p, abs_min, pct_min):
        return DiffDecision(
            False,
            True,
            "price_noise",
            {
                "why": "below threshold",
                "reference": reference_p,
                "curr": curr_p,
                "delta": round(curr_p - (reference_p or curr_p), 2),
            },
        )

    direction = "drop" if curr_p < reference_p else "rise"
    if trail < confirm_streak:
        return DiffDecision(
            False,
            True,
            "await_confirm",
            {"why": f"need {confirm_streak} confirmations", "streak": trail, "reference": reference_p, "curr": curr_p},
        )

    if last_event_at and curr_ts - last_event_at < timedelta(hours=cooldown_hours):
        return DiffDecision(
            False,
            True,
            "cooldown",
            {"why": "cooldown active", "prev": prev_p, "curr": curr_p},
        )

    evt = "price_drop" if direction == "drop" else "price_rise"
    return DiffDecision(
        True,
        False,
        evt,
        {
            "why": "meaningful change confirmed",
            "reference": reference_p,
            "curr": curr_p,
            "delta": round(curr_p - reference_p, 2),
            "pct": round(_pct_change(reference_p, curr_p), 2),
            "confirm_streak": trail,
        },
    )
