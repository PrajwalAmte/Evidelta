from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.base import Base
from app.models.evidence import EvidenceRecord, RawSnapshot


def validate_observed_at(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        observed_at = value
    else:
        text = str(value).strip()
        if not text:
            raise ValueError("observed_at cannot be empty")
        try:
            observed_at = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Invalid observed_at timestamp: {value!r}") from exc

    if observed_at.tzinfo is None:
        raise ValueError("observed_at must be timezone-aware UTC or ISO-8601 with timezone information")

    return observed_at.astimezone(timezone.utc)


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "source": str(item.get("source") or "unknown").lower(),
        "title": item.get("title"),
        "body": item.get("body"),
        "url": item.get("url"),
        "language": str(item.get("language") or "unknown").lower(),
    }
    if normalized["source"] == "forum":
        normalized["source"] = "forum"
    return {key: value for key, value in normalized.items() if value is not None}


class IngestionService:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or settings.database_url
        self.engine = self._build_engine(self.database_url)
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

    def _build_engine(self, database_url: str):
        return create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
        )

    def _compute_hash(self, raw_content: str) -> str:
        return hashlib.sha256(raw_content.encode("utf-8")).hexdigest()

    def _compute_author_hash(self, author_id: str) -> str:
        salted = f"{settings.author_id_salt}:{author_id}"
        return hashlib.sha256(salted.encode("utf-8")).hexdigest()

    def _snapshot_record(
        self, session: Session, source_type: str, source_url: str, payload: str, content_hash: str, author_hash: str | None
    ) -> RawSnapshot:
        existing = session.execute(
            select(RawSnapshot).where(RawSnapshot.content_hash == content_hash)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        snapshot = RawSnapshot(
            source_type=source_type,
            source_url=source_url,
            raw_payload=payload,
            content_hash=content_hash,
            fetched_at=datetime.now(timezone.utc),
            author_hash=author_hash,
        )
        session.add(snapshot)
        session.flush()
        return snapshot

    def ingest_evidence(
        self,
        *,
        source_type: str,
        source_url: str,
        observed_at: datetime,
        raw_content: str | dict[str, Any],
        author_id: str | None = None,
    ) -> dict[str, Any]:
        observed_at = validate_observed_at(observed_at)
        payload = raw_content if isinstance(raw_content, str) else json.dumps(raw_content, sort_keys=True, default=str)
        content_hash = self._compute_hash(payload)
        author_hash = self._compute_author_hash(author_id) if author_id else None

        with self.SessionLocal() as session:
            existing = session.execute(
                select(EvidenceRecord).where(
                    EvidenceRecord.source_url == source_url,
                    EvidenceRecord.content_hash == content_hash,
                )
            ).scalar_one_or_none()
            if existing is not None:
                return self._serialize_record(existing)

            snapshot = self._snapshot_record(session, source_type, source_url, payload, content_hash, author_hash)
            evidence = EvidenceRecord(
                source_type=source_type,
                source_url=source_url,
                observed_at=observed_at,
                fetched_at=datetime.now(timezone.utc),
                content_hash=content_hash,
                author_hash=author_hash,
                snapshot_id=snapshot.id,
            )
            session.add(evidence)
            session.commit()
            session.refresh(evidence)
            return self._serialize_record(evidence)

    def replay_as_of(self, cutoff: datetime) -> list[dict[str, Any]]:
        with self.SessionLocal() as session:
            rows = session.execute(
                select(EvidenceRecord).where(EvidenceRecord.observed_at <= cutoff).order_by(EvidenceRecord.observed_at.asc())
            ).scalars().all()
            return [self._serialize_record(row) for row in rows]

    @staticmethod
    def _serialize_record(record: EvidenceRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "source_type": record.source_type,
            "source_url": record.source_url,
            "observed_at": record.observed_at.isoformat(),
            "fetched_at": record.fetched_at.isoformat(),
            "content_hash": record.content_hash,
            "author_hash": record.author_hash,
            "snapshot_id": record.snapshot_id,
        }


__all__ = ["IngestionService", "normalize_item"]
