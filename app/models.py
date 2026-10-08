from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    base_url: Mapped[str] = mapped_column(String(256))
    adapter: Mapped[str] = mapped_column(String(64))
    priority: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_sku: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(256))
    brand: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(64))
    gtin: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    mpn: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    pack_size: Mapped[int] = mapped_column(Integer, default=1)
    map_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    importance: Mapped[int] = mapped_column(Integer, default=2)


class Listing(Base):
    __tablename__ = "listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    url: Mapped[str] = mapped_column(String(512))
    seller: Mapped[str] = mapped_column(String(128), default="")
    condition: Mapped[str] = mapped_column(String(32), default="new")
    raw_title: Mapped[str] = mapped_column(String(256))
    gtin: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    mpn: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    pack_size: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped["Source"] = relationship()
    product: Mapped[Optional["Product"]] = relationship()


class MatchCandidate(Base):
    __tablename__ = "match_candidates"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    method: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)
    guard_notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/accepted/rejected


class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"))
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shipping: Mapped[float] = mapped_column(Float, default=0.0)
    landed_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    promo_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    parse_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    snapshot_hash: Mapped[str] = mapped_column(String(64), default="")
    page_state: Mapped[str] = mapped_column(String(32), default="ok")  # ok/challenge/empty/parse_fail/rate_limited


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    listing_id: Mapped[Optional[int]] = mapped_column(ForeignKey("listings.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), default="info")
    suppressed: Mapped[bool] = mapped_column(Boolean, default=False)
    reason_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def reason(self) -> dict:
        return json.loads(self.reason_json or "{}")


class MapPolicy(Base):
    __tablename__ = "map_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    map_price: Mapped[float] = mapped_column(Float)
    version: Mapped[str] = mapped_column(String(32), default="v1")
    use_landed: Mapped[bool] = mapped_column(Boolean, default=False)


class MapViolation(Base):
    __tablename__ = "map_violations"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    status: Mapped[str] = mapped_column(String(32), default="detected")
    observed_price: Mapped[float] = mapped_column(Float)
    map_price: Mapped[float] = mapped_column(Float)
    seller: Mapped[str] = mapped_column(String(128))
    evidence_path: Mapped[str] = mapped_column(String(512), default="")
    trap_filtered: Mapped[bool] = mapped_column(Boolean, default=False)
    trap_reason: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ok_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")


class OutboxMessage(Base):
    __tablename__ = "outbox"
    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str] = mapped_column(String(256))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NoiseCounter(Base):
    __tablename__ = "noise_stats"
    id: Mapped[int] = mapped_column(primary_key=True)
    week_key: Mapped[str] = mapped_column(String(16), unique=True)
    suppressed_count: Mapped[int] = mapped_column(Integer, default=0)
