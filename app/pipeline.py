from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import desc
from sqlalchemy.orm import Session

from adapters.registry import ADAPTERS
from config import (
    CONFIRM_STREAK,
    EVIDENCE_DIR,
    EVENT_COOLDOWN_HOURS,
    MAP_CONFIRM_STREAK,
    MATCH_AUTO_THRESHOLD,
    PRICE_ABS_MIN,
    PRICE_PCT_MIN,
    SANDBOX_BASE_URL,
)
from diff.engine import evaluate_price_change
from map.engine import evaluate_map, is_authorized_seller
from match.engine import match_listing_to_products
from models import (
    Event,
    Listing,
    MapPolicy,
    MapViolation,
    MatchCandidate,
    NoiseCounter,
    Observation,
    OutboxMessage,
    Product,
    Run,
    Source,
)
from notify.outbox import enqueue
from rules.engine import is_clearance_price

AUTHORIZED_SELLERS = {
    "authorized": [
        "Authorized Demo Dealer",
        "Shop A",
        "Shop B",
        "Shop C",
        "Shop D",
        "Budget Beans LLC",
    ]
}


def init_schema(db: Session) -> None:
    from database import Base, engine

    Base.metadata.create_all(bind=engine)


def seed_sources(db: Session) -> None:
    if db.query(Source).count():
        return
    rows = [
        ("shop_a", "Synthetic Shop A", f"{SANDBOX_BASE_URL}", "shop_a", 1),
        ("shop_b", "Synthetic Shop B", f"{SANDBOX_BASE_URL}", "shop_b", 1),
        ("shop_c", "Synthetic Shop C", f"{SANDBOX_BASE_URL}", "shop_c", 2),
        ("shop_d", "Synthetic Shop D", f"{SANDBOX_BASE_URL}", "shop_d", 2),
        ("market_x", "Synthetic Market X", f"{SANDBOX_BASE_URL}", "market_x", 1),
    ]
    for key, name, url, adapter, pri in rows:
        db.add(Source(key=key, name=name, base_url=url, adapter=adapter, priority=pri))
    db.commit()


def seed_products_from_listings(db: Session, sample_rows: list[dict]) -> None:
    if db.query(Product).count():
        return
    seen: set[str] = set()
    for row in sample_rows:
        gtin = row.get("gtin")
        if not gtin or gtin in seen:
            continue
        seen.add(gtin)
        sku = gtin[-6:]
        db.add(
            Product(
                canonical_sku=f"P-{sku}",
                title=row.get("raw_title") or "Synthetic Product",
                brand=row.get("brand") or "SandboxRoast",
                model=row.get("model") or "SB100",
                gtin=gtin,
                mpn=row.get("mpn"),
                pack_size=int(row.get("pack_size") or 1),
                map_price=float(row.get("map_price") or 0) if row.get("map_price") else None,
                importance=2,
            )
        )
    db.commit()
    # enrich MAP from sandbox catalog file if present
    catalog_path = Path(__file__).resolve().parent.parent / "sandbox" / "data" / "catalog.json"
    if catalog_path.exists():
        catalog = json.loads(catalog_path.read_text())
        by_gtin = {p["gtin"]: p for p in catalog}
        for prod in db.query(Product).all():
            if prod.gtin in by_gtin:
                prod.map_price = by_gtin[prod.gtin].get("map_price")
                prod.title = by_gtin[prod.gtin]["title"]
                prod.pack_size = by_gtin[prod.gtin]["pack_size"]
                db.add(MapPolicy(product_id=prod.id, map_price=prod.map_price or 0, version="demo-v1", use_landed=False))
        db.commit()


def _week_key() -> str:
    return datetime.utcnow().strftime("%Y-W%W")


def bump_noise(db: Session) -> None:
    wk = _week_key()
    row = db.query(NoiseCounter).filter_by(week_key=wk).first()
    if not row:
        row = NoiseCounter(week_key=wk, suppressed_count=0)
        db.add(row)
    row.suppressed_count += 1
    db.commit()


def run_source(db: Session, source: Source) -> Run:
    adapter = ADAPTERS[source.adapter]
    run = Run(source_id=source.id, started_at=datetime.utcnow())
    db.add(run)
    db.commit()

    rows = adapter.iter_listings(source.base_url)
    products = [
        {
            "id": p.id,
            "title": p.title,
            "brand": p.brand,
            "model": p.model,
            "gtin": p.gtin,
            "mpn": p.mpn,
            "pack_size": p.pack_size,
            "capacity_ml": None,
            "color": None,
        }
        for p in db.query(Product).all()
    ]

    ok = fail = 0
    for row in rows:
        page_state = row.get("page_state", "ok")
        if row.get("meta_only"):
            fail += 1
            db.add(
                Observation(
                    listing_id=_ensure_listing(db, source, row).id,
                    price=None,
                    shipping=0,
                    landed_price=None,
                    in_stock=False,
                    parse_confidence=row.get("parse_confidence", 0),
                    page_state=page_state,
                    snapshot_hash=row.get("snapshot_hash", ""),
                )
            )
            continue
        listing = _ensure_listing(db, source, row)
        if not listing.product_id:
            m = match_listing_to_products(row, products, MATCH_AUTO_THRESHOLD)
            if m.accepted and m.product_id:
                listing.product_id = m.product_id
            elif m.product_id and not m.accepted:
                db.add(
                    MatchCandidate(
                        listing_id=listing.id,
                        product_id=m.product_id,
                        method=m.method,
                        confidence=m.confidence,
                        guard_notes=m.guard_notes,
                        status="rejected" if m.guard_notes else "pending",
                    )
                )
            db.commit()

        price = row.get("price")
        shipping = float(row.get("shipping") or 0)
        landed = row.get("landed_price") or (price + shipping if price is not None else None)
        obs = Observation(
            listing_id=listing.id,
            price=price,
            shipping=shipping,
            landed_price=landed,
            in_stock=bool(row.get("in_stock", True)),
            promo_flag=False,
            parse_confidence=float(row.get("parse_confidence", 1.0)),
            page_state=page_state,
            snapshot_hash=row.get("snapshot_hash", ""),
        )
        db.add(obs)
        db.commit()
        if page_state == "ok" and price is not None:
            ok += 1
            _process_price_and_map(db, listing, obs)
        else:
            fail += 1

    run.finished_at = datetime.utcnow()
    run.ok_count = ok
    run.fail_count = fail
    run.notes = f"rows={len(rows)}"
    db.commit()
    return run


def _ensure_listing(db: Session, source: Source, row: dict) -> Listing:
    existing = db.query(Listing).filter_by(source_id=source.id, url=row["url"]).first()
    if existing:
        existing.raw_title = row.get("raw_title") or existing.raw_title
        existing.seller = row.get("seller") or existing.seller
        existing.condition = row.get("condition") or existing.condition
        existing.pack_size = int(row.get("pack_size") or existing.pack_size)
        existing.gtin = row.get("gtin") or existing.gtin
        existing.mpn = row.get("mpn") or existing.mpn
        db.commit()
        return existing
    lst = Listing(
        source_id=source.id,
        url=row["url"],
        seller=row.get("seller") or source.name,
        condition=row.get("condition", "new"),
        raw_title=row.get("raw_title") or "",
        gtin=row.get("gtin"),
        mpn=row.get("mpn"),
        pack_size=int(row.get("pack_size") or 1),
    )
    db.add(lst)
    db.commit()
    db.refresh(lst)
    return lst


def _process_price_and_map(db: Session, listing: Listing, obs: Observation) -> None:
    history = (
        db.query(Observation)
        .filter_by(listing_id=listing.id)
        .order_by(Observation.observed_at.asc())
        .all()
    )
    hist_t = [(h.observed_at, h.price or 0.0, h.page_state, h.parse_confidence) for h in history if h.price is not None]

    last_evt = (
        db.query(Event)
        .filter_by(listing_id=listing.id, suppressed=False)
        .order_by(desc(Event.created_at))
        .first()
    )
    decision = evaluate_price_change(
        hist_t,
        abs_min=PRICE_ABS_MIN,
        pct_min=PRICE_PCT_MIN,
        confirm_streak=CONFIRM_STREAK,
        cooldown_hours=EVENT_COOLDOWN_HOURS,
        last_event_at=last_evt.created_at if last_evt else None,
    )
    if decision.emit:
        evt = Event(
            product_id=listing.product_id,
            listing_id=listing.id,
            event_type=decision.event_type,
            severity="high" if decision.event_type == "price_drop" else "info",
            suppressed=False,
            reason_json=json.dumps(decision.reason),
        )
        db.add(evt)
        enqueue(db, "telegram", f"Alert: {decision.event_type}", json.dumps(decision.reason, indent=2))
        if is_clearance_price(obs.price or 0):
            db.add(
                Event(
                    product_id=listing.product_id,
                    listing_id=listing.id,
                    event_type="clearance_pattern",
                    severity="info",
                    suppressed=False,
                    reason_json=json.dumps({"why": "price ends in .x1", "price": obs.price}),
                )
            )
    elif decision.suppressed:
        db.add(
            Event(
                product_id=listing.product_id,
                listing_id=listing.id,
                event_type=decision.event_type,
                severity="info",
                suppressed=True,
                reason_json=json.dumps(decision.reason),
            )
        )
        bump_noise(db)

    if listing.product_id and obs.price is not None:
        policy = db.query(MapPolicy).filter_by(product_id=listing.product_id).first()
        prod = db.get(Product, listing.product_id)
        map_price = policy.map_price if policy else (prod.map_price or 0)
        below_streak = _count_below_map_streak(history, map_price, policy.use_landed if policy else False)
        ev = evaluate_map(
            condition=listing.condition,
            is_bundle="bundle" in listing.raw_title.lower(),
            list_price=obs.price,
            shipping=obs.shipping,
            map_price=map_price,
            use_landed=policy.use_landed if policy else False,
            streak_below=below_streak,
            required_streak=MAP_CONFIRM_STREAK,
        )
        if ev.filtered_trap:
            db.add(
                MapViolation(
                    listing_id=listing.id,
                    product_id=listing.product_id,
                    status="filtered",
                    observed_price=ev.compare_price,
                    map_price=map_price,
                    seller=listing.seller,
                    trap_filtered=True,
                    trap_reason=ev.trap_reason,
                )
            )
        elif ev.violation and not is_authorized_seller(listing.seller, AUTHORIZED_SELLERS):
            evidence = _write_evidence_stub(listing, obs)
            db.add(
                MapViolation(
                    listing_id=listing.id,
                    product_id=listing.product_id,
                    status="detected",
                    observed_price=ev.compare_price,
                    map_price=map_price,
                    seller=listing.seller,
                    evidence_path=str(evidence),
                    trap_filtered=False,
                )
            )
            enqueue(db, "slack", "MAP violation detected", json.dumps(ev.reason))


def _count_below_map_streak(history: list[Observation], map_price: float, use_landed: bool) -> int:
    streak = 0
    for h in reversed(history):
        if h.page_state != "ok" or h.price is None:
            break
        cmp = (h.price + h.shipping) if use_landed else h.price
        if cmp < map_price:
            streak += 1
        else:
            break
    return streak


def _write_evidence_stub(listing: Listing, obs: Observation) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / f"map_{listing.id}_{int(obs.observed_at.timestamp())}.html"
    path.write_text(
        f"<html><body><h1>Synthetic evidence snapshot</h1>"
        f"<p>Seller: {listing.seller}</p><p>Price: {obs.price}</p>"
        f"<p>URL: {listing.url}</p></body></html>"
    )
    return path


def run_all_sources(db: Session) -> list[Run]:
    runs = []
    for src in db.query(Source).filter_by(enabled=True).order_by(Source.priority):
        runs.append(run_source(db, src))
    return runs
