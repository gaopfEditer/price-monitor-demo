from __future__ import annotations

from datetime import datetime, timedelta

import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from diff.engine import evaluate_price_change, is_significant_change
from fetch.client import detect_page_state
from map.engine import evaluate_map
from match.engine import match_listing_to_products


def test_pack_size_match_rejection():
    products = [{"id": 1, "title": "Demo Grinder Burr Set (2-Pack)", "brand": "X", "model": "DG103", "gtin": "1", "mpn": "m", "pack_size": 2}]
    listing = {"raw_title": "Demo Grinder Burr Single", "gtin": "1", "mpn": "m", "pack_size": 1, "brand": "X", "model": "DG103"}
    res = match_listing_to_products(listing, products, threshold=0.8)
    assert res.accepted is False
    assert "pack_size" in res.guard_notes


def test_two_cent_jitter_suppressed():
    t0 = datetime(2026, 1, 1, 12, 0, 0)
    hist = [
        (t0, 100.00, "ok", 1.0),
        (t0 + timedelta(hours=6), 100.02, "ok", 1.0),
    ]
    d = evaluate_price_change(hist, abs_min=1.0, pct_min=3.0, confirm_streak=2)
    assert d.emit is False
    assert d.suppressed is True
    assert not is_significant_change(100.0, 100.02, 1.0, 3.0)


def test_real_drop_alerts_after_confirmation():
    t0 = datetime(2026, 1, 1, 12, 0, 0)
    hist = [
        (t0, 429.99, "ok", 1.0),
        (t0 + timedelta(hours=6), 429.99, "ok", 1.0),
        (t0 + timedelta(hours=12), 349.99, "ok", 1.0),
        (t0 + timedelta(hours=18), 349.99, "ok", 1.0),
    ]
    d = evaluate_price_change(hist, abs_min=1.0, pct_min=3.0, confirm_streak=2)
    assert d.emit is True
    assert d.event_type == "price_drop"


def test_flash_sale_24h_suppressed():
    t0 = datetime(2026, 1, 1, 12, 0, 0)
    hist = [
        (t0, 200.0, "ok", 1.0),
        (t0 + timedelta(hours=6), 170.0, "ok", 1.0),
        (t0 + timedelta(hours=30), 200.0, "ok", 1.0),
    ]
    d = evaluate_price_change(hist, abs_min=1.0, pct_min=3.0, confirm_streak=2)
    assert d.emit is False
    assert d.event_type == "flash_sale"


def test_map_false_positive_traps():
    used = evaluate_map(condition="used", is_bundle=False, list_price=150, shipping=0, map_price=400, use_landed=False, streak_below=2)
    assert used.filtered_trap is True
    ship = evaluate_map(condition="new", is_bundle=False, list_price=399, shipping=89, map_price=400, use_landed=False, streak_below=2)
    assert ship.filtered_trap is True
    real = evaluate_map(condition="new", is_bundle=False, list_price=350, shipping=0, map_price=400, use_landed=False, streak_below=2)
    assert real.violation is True


def test_challenge_page_detection():
    html = "<html><head><title>Just a moment...</title></head><body><div id='cf-challenge'>x</div></body></html>"
    assert detect_page_state(503, html) == "challenge"
    assert detect_page_state(429, "rate limited") == "rate_limited"
