from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

PACK_RE = re.compile(r"(\d+)\s*[- ]?pack", re.I)
ML_RE = re.compile(r"(\d+)\s*ml", re.I)


@dataclass
class MatchResult:
    product_id: int | None
    method: str
    confidence: float
    accepted: bool
    guard_notes: str = ""


def normalize_model(text: str) -> str | None:
    m = re.search(r"\b([A-Z]{2,}\d{2,})\b", text.upper())
    return m.group(1) if m else None


def extract_pack_size(title: str, fallback: int = 1) -> int:
    m = PACK_RE.search(title)
    return int(m.group(1)) if m else fallback


def attribute_guards(listing: dict, product: dict) -> tuple[bool, str]:
    lp = int(listing.get("pack_size") or extract_pack_size(listing.get("raw_title", ""), 1))
    pp = int(product.get("pack_size") or 1)
    if lp != pp:
        return False, f"pack_size mismatch ({lp} vs {pp})"
    lc = listing.get("capacity_ml")
    pc = product.get("capacity_ml")
    if lc and pc and lc != pc:
        return False, f"capacity mismatch ({lc} vs {pc})"
    if listing.get("color") and product.get("color") and listing["color"] != product["color"]:
        return False, f"color mismatch"
    return True, ""


def match_listing_to_products(listing: dict, products: list[dict], threshold: float = 0.8) -> MatchResult:
    gtin = listing.get("gtin")
    mpn = listing.get("mpn")
    title = listing.get("raw_title") or listing.get("title") or ""

    for p in products:
        if gtin and p.get("gtin") and gtin == p["gtin"]:
            ok, note = attribute_guards(listing, p)
            if not ok:
                return MatchResult(p["id"], "gtin_guard", 1.0, False, note)
            return MatchResult(p["id"], "gtin", 1.0, True)

    for p in products:
        if mpn and p.get("mpn") and mpn.upper() == p["mpn"].upper():
            ok, note = attribute_guards(listing, p)
            if not ok:
                return MatchResult(p["id"], "mpn_guard", 0.9, False, note)
            return MatchResult(p["id"], "mpn", 0.9, True)

    brand = listing.get("brand")
    model = listing.get("model") or normalize_model(title)
    if brand and model:
        for p in products:
            if p.get("brand") == brand and p.get("model") == model:
                ok, note = attribute_guards(listing, p)
                if not ok:
                    return MatchResult(p["id"], "brand_model_guard", 0.9, False, note)
                return MatchResult(p["id"], "brand_model", 0.9, True)

    best: tuple[float, dict | None, str] = (0.0, None, "")
    for p in products:
        score = fuzz.token_set_ratio(title, p.get("title", "")) / 100.0
        ok, note = attribute_guards(listing, p)
        if not ok:
            if score >= threshold:
                return MatchResult(p["id"], "fuzzy_guard", score, False, note)
            continue
        if score > best[0]:
            best = (score, p, note)

    score, prod, note = best
    if prod and score >= threshold:
        return MatchResult(prod["id"], "fuzzy", score, True, note)
    if prod and score >= 0.65:
        return MatchResult(prod["id"], "fuzzy_review", score, False, note or "low confidence")
    return MatchResult(None, "none", 0.0, False, "no candidate")
