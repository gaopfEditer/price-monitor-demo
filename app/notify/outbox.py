from __future__ import annotations

from sqlalchemy.orm import Session

from models import OutboxMessage


def enqueue(db: Session, channel: str, subject: str, body: str) -> None:
    db.add(OutboxMessage(channel=channel, subject=subject, body=body))
