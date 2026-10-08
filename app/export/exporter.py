from __future__ import annotations

import csv
import io
from datetime import datetime

from openpyxl import Workbook
from sqlalchemy.orm import Session

from models import Event, Listing, MapViolation, Product


def export_csv(db: Session) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["event_type", "product", "listing_url", "suppressed", "created_at"])
    for e in db.query(Event).order_by(Event.created_at.desc()).limit(500):
        prod = db.get(Product, e.product_id) if e.product_id else None
        listing = db.get(Listing, e.listing_id) if e.listing_id else None
        w.writerow([e.event_type, prod.title if prod else "", listing.url if listing else "", e.suppressed, e.created_at.isoformat()])
    return buf.getvalue()


def export_excel(db: Session) -> bytes:
    wb = Workbook()
    master = wb.active
    master.title = "Master"
    master.append(["SKU", "Title", "Brand", "MAP"])
    for p in db.query(Product).all():
        master.append([p.canonical_sku, p.title, p.brand, p.map_price])

    sheets: list[tuple[str, list]] = [
        ("New", db.query(Event).filter(Event.event_type == "new_listing").order_by(Event.created_at.desc()).limit(200).all()),
        (
            "Price Changes",
            db.query(Event).filter(Event.event_type.in_(["price_drop", "price_rise"])).order_by(Event.created_at.desc()).limit(200).all(),
        ),
        ("MAP", db.query(MapViolation).filter(MapViolation.trap_filtered.is_(False)).order_by(MapViolation.created_at.desc()).limit(200).all()),
        ("Change History", db.query(Event).order_by(Event.created_at.desc()).limit(200).all()),
    ]
    for name, rows in sheets:
        ws = wb.create_sheet(name[:31])
        ws.append(["type", "suppressed", "created_at", "reason"])
        for row in rows:
            if isinstance(row, Event):
                ws.append([row.event_type, row.suppressed, row.created_at.isoformat(), row.reason_json[:120]])
            else:
                ws.append(["map_violation", row.trap_filtered, row.created_at.isoformat(), row.seller])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
