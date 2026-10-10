from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, relationship, mapped_column

from app.db.base import Base


class RawSnapshot(Base):
    __tablename__ = "raw_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    raw_payload: Mapped[str] = mapped_column(Text(), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    author_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    evidence_records: Mapped[list["EvidenceRecord"]] = relationship(back_populates="snapshot")


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    author_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("raw_snapshots.id"), nullable=False)
    snapshot: Mapped[RawSnapshot] = relationship(back_populates="evidence_records")
