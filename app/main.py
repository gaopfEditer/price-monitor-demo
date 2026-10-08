from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from database import SessionLocal
from pipeline import init_schema, seed_sources
from seed import seed_products_from_catalog
from web.routes import router

app = FastAPI(title="Retail Price & MAP Watch", version="1.0.0")
static_dir = Path(__file__).parent / "web" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.include_router(router)


@app.on_event("startup")
def startup():
    db = SessionLocal()
    try:
        init_schema(db)
        seed_sources(db)
        seed_products_from_catalog(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"ok": True}
