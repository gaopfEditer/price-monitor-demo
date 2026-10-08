"""Offline synthetic retail sandbox + time simulator (port 8001)."""
from __future__ import annotations

import copy
import random
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from catalog import load_catalog
from timeline import load_timeline

DATA_DIR = Path(__file__).parent / "data"
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(title="Synthetic Retail Sandbox", version="1.0.0")

catalog = load_catalog(DATA_DIR / "catalog.json")
timeline_doc = load_timeline(DATA_DIR / "timeline.json")

# Mutable simulation state
state: dict[str, Any] = {
    "sim_day": 0,
    "overrides": {},  # (shop, sku) -> dict
    "promos": {},
    "flags": {"shop-c_challenge": False, "shop-d_dom": 0, "rate_limit_hits": 0},
    "request_counts": {},
    "challenge_until": 0.0,
}


def _key(shop: str, sku: str) -> str:
    return f"{shop}|{sku}"


def _product(sku: str) -> dict:
    for p in catalog:
        if p["sku"] == sku:
            return p
    raise HTTPException(404, "SKU not found")


def _listing(shop: str, sku: str) -> dict:
    p = copy.deepcopy(_product(sku))
    ov = state["overrides"].get(_key(shop, sku), {})
    p.update(ov)
    p["sku"] = sku
    p["shop"] = shop
    if shop == "market-x" and "seller" not in p:
        p["seller"] = "Authorized Demo Dealer"
        p["condition"] = "new"
        p["shipping"] = round(random.Random(hash(sku)).uniform(0, 15), 2)
    elif shop != "market-x":
        p["seller"] = shop.replace("-", " ").title()
        p["condition"] = "new"
        p["shipping"] = 0.0 if shop == "shop-a" else round(random.Random(hash(sku)).uniform(5, 12), 2)
    if "in_stock" not in p:
        p["in_stock"] = True
    if "delisted" not in p:
        p["delisted"] = False
    price = p.get("price", p["base_price"])
    promo = state["promos"].get(_key(shop, sku))
    if promo and promo.get("active"):
        price = round(price * (1 - promo["discount_pct"] / 100), 2)
    p["price"] = price
    p["landed_price"] = round(p["price"] + float(p.get("shipping", 0)), 2)
    return p


def apply_day_events(day: int) -> list[str]:
    applied: list[str] = []
    for block in timeline_doc["days"]:
        if block["day"] != day:
            continue
        for ch in block.get("changes", []):
            shop, sku = ch["target"], ch["sku"]
            k = _key(shop, sku)
            ov = state["overrides"].setdefault(k, {})
            mode = ch["mode"]
            if mode == "jitter_cents":
                base = ov.get("price", _product(sku)["base_price"])
                ov["price"] = round(base + ch["cents"] / 100, 2)
            elif mode == "set_price":
                ov["price"] = ch["price"]
            elif mode == "flash":
                state["promos"][k] = {"active": True, "discount_pct": ch["discount_pct"], "ends_day": day + 1}
            elif mode == "flash_end":
                if k in state["promos"]:
                    state["promos"][k]["active"] = False
            elif mode == "map_breach":
                ov.update({"price": ch.get("price", _product(sku)["map_price"] - 40), "seller": ch["seller"], "condition": "new"})
            elif mode == "used_listing":
                ov.update({"price": ch["price"], "seller": ch["seller"], "condition": "used"})
            elif mode == "low_listing_high_shipping":
                ov.update({"price": ch["price"], "shipping": ch["shipping"], "seller": ch["seller"], "condition": "new"})
            elif mode == "out_of_stock":
                ov["in_stock"] = False
            elif mode == "in_stock":
                ov["in_stock"] = True
            elif mode == "delisted":
                ov["delisted"] = True
            elif mode == "relisted":
                ov["delisted"] = False
            elif mode == "clearance_price":
                ov["price"] = ch["price"]
            applied.append(f"{shop}:{sku}:{mode}")
        for pr in block.get("promos", []):
            k = _key(pr["target"], pr["sku"])
            if pr["mode"] == "flash":
                state["promos"][k] = {"active": True, "discount_pct": pr["discount_pct"], "ends_day": state["sim_day"] + 1}
            elif pr["mode"] == "flash_end":
                if k in state["promos"]:
                    state["promos"][k]["active"] = False
        for fl in block.get("flags", []):
            if fl["mode"] == "challenge_burst":
                state["flags"]["shop-c_challenge"] = True
                state["challenge_until"] = time.time() + 3600
            elif fl["mode"] == "dom_revision":
                state["flags"]["shop-d_dom"] = fl.get("version", 1)
    return applied


@app.get("/")
def root():
    return {
        "service": "synthetic-retail-sandbox",
        "sim_day": state["sim_day"],
        "shops": ["shop-a", "shop-b", "shop-c", "shop-d", "market-x"],
        "admin_tick": "/admin/tick?days=1",
    }


@app.post("/admin/reset")
def admin_reset():
    state["sim_day"] = 0
    state["overrides"] = {}
    state["promos"] = {}
    state["flags"] = {"shop-c_challenge": False, "shop-d_dom": 0, "rate_limit_hits": 0}
    state["request_counts"] = {}
    state["challenge_until"] = 0.0
    return {"ok": True, "sim_day": 0}


@app.post("/admin/tick")
def admin_tick(days: int = Query(1, ge=1, le=30)):
    applied_all: list[str] = []
    for _ in range(days):
        state["sim_day"] += 1
        applied_all.extend(apply_day_events(state["sim_day"]))
    return {"sim_day": state["sim_day"], "applied": applied_all}


def _paginate(items: list, page: int, per_page: int = 12):
    start = (page - 1) * per_page
    return items[start : start + per_page], len(items)


# --- shop-a: static HTML pagination ---
@app.get("/shop-a/", response_class=HTMLResponse)
@app.get("/shop-a/page/{page}", response_class=HTMLResponse)
def shop_a(request: Request, page: int = 1):
    items, total = _paginate(catalog, page)
    listings = [_listing("shop-a", p["sku"]) for p in items if not _listing("shop-a", p["sku"]).get("delisted")]
    return templates.TemplateResponse(
        "shop_a.html",
        {"request": request, "listings": listings, "page": page, "total_pages": (total + 11) // 12},
    )


# --- shop-b: JSON API + SPA shell ---
@app.get("/shop-b/api/products")
def shop_b_api(page: int = 1):
    items, total = _paginate(catalog, page)
    rows = []
    for p in items:
        L = _listing("shop-b", p["sku"])
        if L.get("delisted"):
            continue
        rows.append(
            {
                "id": p["sku"],
                "name": p["title"],
                "brand": p["brand"],
                "model": p["model"],
                "gtin": p["gtin"],
                "mpn": p["mpn"],
                "price": L["price"],
                "shipping": L["shipping"],
                "inStock": L["in_stock"],
                "packSize": p["pack_size"],
            }
        )
    return {"page": page, "total": total, "products": rows}


@app.get("/shop-b/", response_class=HTMLResponse)
def shop_b_spa(request: Request):
    return templates.TemplateResponse("shop_b_spa.html", {"request": request})


# --- shop-c: rate limit + challenge ---
def _shop_c_gate(request: Request) -> Response | None:
    ip = request.client.host if request.client else "unknown"
    counts = state["request_counts"]
    counts[ip] = counts.get(ip, 0) + 1
    if counts[ip] > 8:
        state["flags"]["rate_limit_hits"] += 1
        return JSONResponse(
            {"error": "rate_limited", "retry_after": 30},
            status_code=429,
            headers={"Retry-After": "30"},
        )
    if state["flags"].get("shop-c_challenge") and time.time() < state["challenge_until"]:
        if random.random() < 0.35:
            return HTMLResponse(
                "<html><head><title>Just a moment...</title></head>"
                "<body><h1>Security Check</h1><p>Please complete the challenge.</p>"
                "<div id='cf-challenge'>cloudflare-style-challenge-page</div></body></html>",
                status_code=503,
            )
    return None


@app.get("/shop-c/page/{page}", response_class=HTMLResponse)
def shop_c(request: Request, page: int = 1):
    blocked = _shop_c_gate(request)
    if blocked:
        return blocked
    items, total = _paginate(catalog, page)
    listings = [_listing("shop-c", p["sku"]) for p in items]
    return templates.TemplateResponse(
        "shop_c.html",
        {"request": request, "listings": listings, "page": page, "total_pages": (total + 11) // 12},
    )


# --- shop-d: DOM revisions ---
@app.get("/shop-d/page/{page}", response_class=HTMLResponse)
def shop_d(request: Request, page: int = 1):
    items, total = _paginate(catalog, page)
    listings = [_listing("shop-d", p["sku"]) for p in items]
    dom_v = state["flags"].get("shop-d_dom", 0)
    tpl = "shop_d_v0.html" if dom_v == 0 else "shop_d_v1.html"
    return templates.TemplateResponse(
        tpl,
        {"request": request, "listings": listings, "page": page, "total_pages": (total + 11) // 12, "dom_version": dom_v},
    )


# --- market-x: multi seller ---
@app.get("/market-x/listings")
def market_x(page: int = 1):
    items, total = _paginate(catalog, page)
    rows = []
    for p in items:
        base = _listing("market-x", p["sku"])
        rows.append(base)
        # decoy: single vs 2-pack for SKU-004 on alternate seller
        if p["sku"] == timeline_doc["demo_skus"]["pack_trap"]:
            alt = copy.deepcopy(base)
            alt["seller"] = "Value Pack Outlet"
            alt["title"] = p["title"].replace("(2-Pack)", "").replace("Grinder Burr Set", "Grinder Burr Single")
            alt["pack_size"] = 1
            alt["price"] = round(base["price"] * 0.55, 2)
            rows.append(alt)
    return {"page": page, "listings": rows}


@app.get("/market-x/", response_class=HTMLResponse)
def market_x_html(request: Request):
    return templates.TemplateResponse("market_x.html", {"request": request})
