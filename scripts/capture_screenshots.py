#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
BASE = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")

PAGES = [
    ("01-overview", "/"),
    ("02-events", "/events"),
    ("03-events-suppressed", "/events?show_suppressed=1"),
    ("04-match-queue", "/match-queue"),
    ("05-map-board", "/map"),
    ("06-sources-health", "/sources"),
    ("07-rules-export", "/rules"),
]


def ensure_server() -> subprocess.Popen | None:
    try:
        import httpx

        httpx.get(BASE + "/health", timeout=2)
        return None
    except Exception:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "app")
        demo_db = ROOT / "data" / "demo_readonly.db"
        default_db = demo_db if demo_db.is_file() else ROOT / "data" / "app.db"
        env.setdefault("DATABASE_URL", f"sqlite:///{default_db.resolve()}")
        if default_db == demo_db:
            env.setdefault("READONLY", "1")
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(ROOT / "app"),
            env=env,
        )
        for _ in range(30):
            time.sleep(0.5)
            try:
                import httpx

                if httpx.get(BASE + "/health", timeout=2).status_code == 200:
                    return proc
            except Exception:
                continue
        proc.kill()
        raise RuntimeError("App server failed to start")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    proc = ensure_server()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            # product detail if SKU-002 exists
            import httpx

            try:
                o = httpx.get(BASE + "/", timeout=10)
            except Exception:
                o = None
            for name, path in PAGES:
                page.goto(BASE + path, wait_until="networkidle")
                page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
            # attempt product detail via DB
            demo_db = ROOT / "data" / "demo_readonly.db"
            default_db = demo_db if demo_db.is_file() else ROOT / "data" / "app.db"
            env_db = os.getenv("DATABASE_URL", f"sqlite:///{default_db}")
            sys.path.insert(0, str(ROOT / "app"))
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from models import Product

            engine = create_engine(env_db, connect_args={"check_same_thread": False})
            Session = sessionmaker(bind=engine)
            db = Session()
            p2 = db.query(Product).filter(Product.canonical_sku == "SKU-002").first()
            if p2:
                page.goto(f"{BASE}/products/{p2.id}", wait_until="networkidle")
                page.screenshot(path=str(OUT / "08-product-detail.png"), full_page=True)
            browser.close()
    finally:
        if proc:
            proc.terminate()


if __name__ == "__main__":
    main()
