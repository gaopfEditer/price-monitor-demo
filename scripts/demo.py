#!/usr/bin/env python3
"""Run 14-day sandbox simulation and ingest observations (offline demo story)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "sandbox"))

from catalog import save_catalog  # noqa: E402
from timeline import save_timeline  # noqa: E402
from config import DATABASE_URL, SANDBOX_BASE_URL  # noqa: E402
from database import Base, SessionLocal, engine  # noqa: E402
from pipeline import init_schema, run_all_sources, seed_sources  # noqa: E402
from seed import seed_products_from_catalog  # noqa: E402


def reset_db() -> None:
    if DATABASE_URL.startswith("sqlite"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
        if db_path.startswith("/"):
            path = Path(db_path)
        else:
            path = ROOT / db_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.unlink()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def main() -> int:
    data_dir = ROOT / "sandbox" / "data"
    save_catalog(data_dir / "catalog.json")
    save_timeline(data_dir / "timeline.json")

    sandbox = SANDBOX_BASE_URL.rstrip("/")
    with httpx.Client(base_url=sandbox, timeout=120) as client:
        try:
            client.get("/")
        except httpx.HTTPError as exc:
            print(f"Sandbox not reachable at {sandbox}: {exc}", file=sys.stderr)
            return 1
        client.post("/admin/reset")

    reset_db()
    db = SessionLocal()
    try:
        init_schema(db)
        seed_sources(db)
        seed_products_from_catalog(db)
        with httpx.Client(base_url=sandbox, timeout=120) as client:
            for day in range(1, 15):
                tick = client.post("/admin/tick", params={"days": 1})
                tick.raise_for_status()
                print(f"Day {day}: {tick.json().get('applied', [])[:3]}...")
                run_all_sources(db)
    finally:
        db.close()

    # Copy DB for Vercel read-only bundle
    if DATABASE_URL.startswith("sqlite"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
        src = Path(db_path) if db_path.startswith("/") else ROOT / db_path
        if src.exists():
            dest = ROOT / "data" / "demo_readonly.db"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src.read_bytes())

    summary_path = ROOT / "data" / "demo_summary.json"
    db = SessionLocal()
    try:
        from models import Event, MapViolation, MatchCandidate

        summary = {
            "events_total": db.query(Event).count(),
            "events_pushed": db.query(Event).filter_by(suppressed=False).count(),
            "events_suppressed": db.query(Event).filter_by(suppressed=True).count(),
            "map_detected": db.query(MapViolation).filter_by(trap_filtered=False, status="detected").count(),
            "map_traps_filtered": db.query(MapViolation).filter_by(trap_filtered=True).count(),
            "match_rejected": db.query(MatchCandidate).filter_by(status="rejected").count(),
        }
        summary_path.write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
