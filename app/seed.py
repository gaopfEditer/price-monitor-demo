from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from models import MapPolicy, Product


def seed_products_from_catalog(db: Session, catalog_path: Path | None = None) -> None:
    if db.query(Product).count():
        return
    catalog_path = catalog_path or Path(__file__).resolve().parent.parent / "sandbox" / "data" / "catalog.json"
    if not catalog_path.exists():
        import subprocess
        import sys

        subprocess.check_call([sys.executable, str(catalog_path.parent.parent / "catalog.py"), str(catalog_path)])
    catalog = json.loads(catalog_path.read_text())
    for p in catalog:
        prod = Product(
            canonical_sku=p["sku"],
            title=p["title"],
            brand=p["brand"],
            model=p["model"],
            gtin=p["gtin"],
            mpn=p["mpn"],
            pack_size=p["pack_size"],
            map_price=p.get("map_price"),
            importance=1 if p["sku"] in {"SKU-005", "SKU-002"} else 2,
        )
        db.add(prod)
        db.flush()
        db.add(MapPolicy(product_id=prod.id, map_price=p.get("map_price") or 0, version="demo-v1", use_landed=False))
    db.commit()
