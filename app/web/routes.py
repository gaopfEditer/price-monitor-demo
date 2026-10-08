from __future__ import annotations

import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from config import CONFIG_DIR, EVIDENCE_DIR
from database import get_db
from export.exporter import export_csv, export_excel
from models import Event, Listing, MapViolation, MatchCandidate, Observation, OutboxMessage, Product, Run, Source
from pipeline import run_all_sources
from web.kpi import (
    count_events_24h_pushed,
    count_events_pushed,
    count_events_total,
    count_map_open,
    count_map_traps_filtered,
    count_match_queue,
    count_suppressed_events,
    count_tracked_skus,
    query_events,
    query_map_violations,
    query_match_queue,
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter()

ROOT = Path(__file__).resolve().parent.parent.parent


def _evidence_basename(stored: str) -> str:
    if not stored:
        return ""
    name = Path(stored).name
    if name != stored and ("/" in stored or stored.startswith("/")):
        return name
    return stored


@router.get("/evidence/{evidence_id}", response_class=HTMLResponse)
def evidence_stub(evidence_id: str):
    if not evidence_id or evidence_id != Path(evidence_id).name or ".." in evidence_id:
        raise HTTPException(status_code=404, detail="Not found")
    for base in (EVIDENCE_DIR, ROOT / "data" / "evidence"):
        path = base / evidence_id
        if path.is_file():
            return HTMLResponse(path.read_text())
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/", response_class=HTMLResponse)
def overview(request: Request, db: Session = Depends(get_db)):
    sku_count = count_tracked_skus(db)
    events_24h = count_events_24h_pushed(db)
    map_open = count_map_open(db)
    map_traps = count_map_traps_filtered(db)
    match_queue_n = count_match_queue(db)
    suppressed_week = count_suppressed_events(db, days=7)
    sources = db.query(Source).all()
    health = []
    for s in sources:
        last_run = db.query(Run).filter_by(source_id=s.id).order_by(desc(Run.started_at)).first()
        health.append({"source": s, "last_run": last_run})
    pushed = count_events_pushed(db)
    detected = count_events_total(db)
    return templates.TemplateResponse(
        "overview.html",
        {
            "request": request,
            "sku_count": sku_count,
            "events_24h": events_24h,
            "map_open": map_open,
            "map_traps": map_traps,
            "match_queue_n": match_queue_n,
            "suppressed_week": suppressed_week,
            "health": health,
            "pushed": pushed,
            "detected": detected,
        },
    )


@router.get("/products", response_class=HTMLResponse)
def products_index(request: Request, db: Session = Depends(get_db)):
    total = count_tracked_skus(db)
    products = db.query(Product).order_by(Product.canonical_sku).all()
    return templates.TemplateResponse(
        "products.html",
        {"request": request, "products": products, "total": total},
    )


@router.get("/products/{product_id}", response_class=HTMLResponse)
def product_detail(product_id: int, request: Request, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    listings = db.query(Listing).filter_by(product_id=product_id).all()
    series = []
    for lst in listings:
        obs = db.query(Observation).filter_by(listing_id=lst.id).order_by(Observation.observed_at).all()
        series.append({"listing": lst, "observations": obs})
    events = db.query(Event).filter_by(product_id=product_id).order_by(desc(Event.created_at)).limit(20).all()
    return templates.TemplateResponse(
        "product_detail.html",
        {"request": request, "product": product, "series": series, "events": events},
    )


@router.get("/events", response_class=HTMLResponse)
def events_feed(
    request: Request,
    db: Session = Depends(get_db),
    show_suppressed: int = 0,
    hours: int | None = None,
    days: int | None = None,
):
    q = query_events(db, show_suppressed=bool(show_suppressed), hours=hours, days=days if show_suppressed else None)
    events = q.limit(500).all()
    list_count = len(events)
    return templates.TemplateResponse(
        "events.html",
        {
            "request": request,
            "events": events,
            "show_suppressed": show_suppressed,
            "hours": hours,
            "days": days,
            "list_count": list_count,
        },
    )


@router.get("/match-queue", response_class=HTMLResponse)
def match_queue(request: Request, db: Session = Depends(get_db)):
    pending = query_match_queue(db).all()
    rows = []
    for m in pending:
        rows.append({"m": m, "listing": db.get(Listing, m.listing_id), "product": db.get(Product, m.product_id)})
    return templates.TemplateResponse(
        "match_queue.html",
        {"request": request, "rows": rows, "queue_count": len(rows)},
    )


@router.post("/match-queue/{cid}/confirm")
def match_confirm(cid: int, db: Session = Depends(get_db)):
    m = db.get(MatchCandidate, cid)
    if m:
        m.status = "accepted"
        lst = db.get(Listing, m.listing_id)
        if lst:
            lst.product_id = m.product_id
        db.commit()
    return Response(status_code=204)


@router.get("/map", response_class=HTMLResponse)
def map_board(request: Request, db: Session = Depends(get_db), scope: str | None = None):
    if scope not in (None, "open", "traps"):
        scope = None
    violations = query_map_violations(db, scope=scope).limit(50).all()
    rows = []
    for v in violations:
        rows.append(
            {
                "v": v,
                "listing": db.get(Listing, v.listing_id),
                "product": db.get(Product, v.product_id),
                "evidence_id": _evidence_basename(v.evidence_path),
            }
        )
    return templates.TemplateResponse(
        "map_board.html",
        {"request": request, "rows": rows, "scope": scope, "board_count": len(rows)},
    )


@router.get("/sources", response_class=HTMLResponse)
def sources_health(request: Request, db: Session = Depends(get_db)):
    stats = []
    for s in db.query(Source).all():
        runs = db.query(Run).filter_by(source_id=s.id).order_by(desc(Run.started_at)).limit(10).all()
        obs = (
            db.query(Observation.page_state, func.count(Observation.id))
            .join(Listing, Listing.id == Observation.listing_id)
            .filter(Listing.source_id == s.id)
            .group_by(Observation.page_state)
            .all()
        )
        stats.append({"source": s, "runs": runs, "states": dict(obs)})
    return templates.TemplateResponse("sources_health.html", {"request": request, "stats": stats})


@router.get("/rules", response_class=HTMLResponse)
def rules_export(request: Request, db: Session = Depends(get_db)):
    rules_path = CONFIG_DIR / "rules.yaml"
    rules_text = rules_path.read_text() if rules_path.exists() else "# rules\n"
    outbox = db.query(OutboxMessage).order_by(desc(OutboxMessage.created_at)).limit(30).all()
    return templates.TemplateResponse(
        "rules_export.html",
        {"request": request, "rules_text": rules_text, "outbox": outbox},
    )


@router.post("/rules/save")
def rules_save(content: str = Form(...)):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "rules.yaml").write_text(content)
    return Response(status_code=204)


@router.get("/export/csv")
def download_csv(db: Session = Depends(get_db)):
    return Response(content=export_csv(db), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=events.csv"})


@router.get("/export/excel")
def download_excel(db: Session = Depends(get_db)):
    data = export_excel(db)
    return Response(content=data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=export.xlsx"})


@router.post("/api/run")
def api_run(db: Session = Depends(get_db)):
    runs = run_all_sources(db)
    return {"runs": [{"id": r.id, "ok": r.ok_count, "fail": r.fail_count} for r in runs]}
