"""Shared KPI queries — overview and board views must use these definitions."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import desc
from sqlalchemy.orm import Session

from models import Event, Listing, MapViolation, MatchCandidate, Product


def count_tracked_skus(db: Session) -> int:
    return db.query(Product).count()


def count_events_24h_pushed(db: Session) -> int:
    since = datetime.utcnow() - timedelta(hours=24)
    return (
        db.query(Event)
        .filter(Event.created_at >= since, Event.suppressed.is_(False))
        .count()
    )


def count_events_pushed(db: Session) -> int:
    return db.query(Event).filter(Event.suppressed.is_(False)).count()


def count_events_total(db: Session) -> int:
    return db.query(Event).count()


def count_suppressed_events(db: Session, *, days: int | None = None) -> int:
    q = db.query(Event).filter(Event.suppressed.is_(True))
    if days is not None:
        since = datetime.utcnow() - timedelta(days=days)
        q = q.filter(Event.created_at >= since)
    return q.count()


def count_map_open(db: Session) -> int:
    return (
        db.query(MapViolation)
        .filter(MapViolation.trap_filtered.is_(False), MapViolation.status == "detected")
        .count()
    )


def count_map_traps_filtered(db: Session) -> int:
    return db.query(MapViolation).filter(MapViolation.trap_filtered.is_(True)).count()


def count_match_queue(db: Session) -> int:
    return (
        db.query(MatchCandidate)
        .filter(MatchCandidate.status.in_(["pending", "rejected"]))
        .count()
    )


def query_map_violations(db: Session, scope: str | None = None):
    q = db.query(MapViolation).order_by(desc(MapViolation.created_at))
    if scope == "open":
        q = q.filter(MapViolation.trap_filtered.is_(False), MapViolation.status == "detected")
    elif scope == "traps":
        q = q.filter(MapViolation.trap_filtered.is_(True))
    return q


def query_match_queue(db: Session):
    return db.query(MatchCandidate).filter(MatchCandidate.status.in_(["pending", "rejected"]))


def query_events(
    db: Session,
    *,
    show_suppressed: bool = False,
    hours: int | None = None,
    days: int | None = None,
):
    q = db.query(Event).order_by(desc(Event.created_at))
    if not show_suppressed:
        q = q.filter(Event.suppressed.is_(False))
    elif days is not None:
        since = datetime.utcnow() - timedelta(days=days)
        q = q.filter(Event.created_at >= since)
    if hours is not None:
        since = datetime.utcnow() - timedelta(hours=hours)
        q = q.filter(Event.created_at >= since)
    return q
