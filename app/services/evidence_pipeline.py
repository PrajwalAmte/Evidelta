from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.models.evidence import EvidenceRecord, RawSnapshot
from app.services.change_detection import cluster_evidence
from app.services.extraction import classify_report, resolve_dimension, resolve_product
from app.services.ingestion import IngestionService


def _parse_raw_payload(payload: str) -> dict[str, Any]:
    try:
        parsed = json.loads(payload)
        if isinstance(parsed, dict):
            return {k: parsed.get(k) for k in parsed.keys()}
    except (TypeError, ValueError):
        pass
    return {"body": payload}


def _classify_record(source_url: str, payload: dict[str, Any], source_type: str) -> dict[str, Any]:
    probe_payload = payload.get("probe") if isinstance(payload.get("probe"), dict) else {}
    title = str(payload.get("title") or "")
    body = str(payload.get("body") or payload.get("content") or payload.get("message") or "")
    report = {"title": title, "body": body, "url": source_url, "source": source_type}
    classification = classify_report(report)
    body_text = " ".join(part for part in [title, body] if part)
    product = (
        str(probe_payload.get("product") or "").strip()
        or resolve_product(body_text)
        or resolve_product(source_url)  # URL is a fallback only
        or "unknown"
    )
    text_dimension = resolve_dimension(body_text) or classification.get("dimension")
    probe_dimension = str(probe_payload.get("dimension") or "").strip()
    # Use probe dimension only when the text also supports it; never promote on URL alone.
    if source_type == "probe" and probe_dimension and probe_dimension != text_dimension:
        dimension = "unknown"
    else:
        dimension = probe_dimension or text_dimension or "unknown"
    provider = source_type
    if source_type in {"status_page", "statuspage"}:
        classification["provider_acknowledged"] = True
    if source_type == "probe":
        probe_status = str(probe_payload.get("status") or "").strip().lower()
        if probe_status:
            classification["measurement_reproduced"] = probe_status in {"watch", "degraded", "critical", "elevated"}
        else:
            classification["measurement_reproduced"] = bool(payload.get("measurement_reproduced", False))
        classification["contains_reproducible_example"] = True
        classification["first_hand"] = True
    return {
        "provider": provider,
        "source_type": source_type,
        "source_url": source_url,
        "product": product,
        "dimension": dimension,
        "classification": classification,
    }


class EvidencePipeline:
    def __init__(self, ingestion: IngestionService | None = None) -> None:
        self.ingestion = ingestion or IngestionService()

    def _load_records(self, *, product: str = "all", lookback_days: int = 30) -> list[dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        with self.ingestion.SessionLocal() as session:
            rows = session.execute(
                select(EvidenceRecord, RawSnapshot)
                .join(RawSnapshot, EvidenceRecord.snapshot_id == RawSnapshot.id)
                .where(EvidenceRecord.observed_at >= cutoff)
                .order_by(EvidenceRecord.observed_at.asc())
            ).all()

        prepared: list[dict[str, Any]] = []
        for evidence, snapshot in rows:
            payload = _parse_raw_payload(snapshot.raw_payload)
            classified = _classify_record(evidence.source_url, payload, evidence.source_type)
            if product != "all" and classified["product"] != product and classified["provider"] != product and evidence.source_type != product:
                continue
            prepared.append(
                {
                    "id": evidence.id,
                    "evidence_id": evidence.id,
                    "provider": classified["provider"],
                    "source_type": evidence.source_type,
                    "source_url": evidence.source_url,
                    "observed_at": evidence.observed_at.isoformat(),
                    "product": classified["product"],
                    "dimension": classified["dimension"],
                    "classification": classified["classification"],
                    "title": str(payload.get("title") or ""),
                    "body": str(payload.get("body") or payload.get("content") or payload.get("message") or ""),
                }
            )
        return prepared

    def build_candidate_changes(self, *, product: str = "all", lookback_days: int = 30, limit: int = 25) -> list[dict[str, Any]]:
        records = self._load_records(product=product, lookback_days=lookback_days)
        clusters = cluster_evidence(records)
        status_rank = {
            "acknowledged": 4,
            "measured": 3,
            "corroborated": 2,
            "candidate": 1,
            "insufficient_evidence": 0,
        }
        clusters.sort(
            key=lambda item: (
                0 if str(item.get("dimension", "unknown")) != "unknown" else -1,
                status_rank.get(str(item.get("status", "candidate")), 0),
                int(item.get("independent_reports", 0)),
                int(item.get("evidence_count", 0)),
            ),
            reverse=True,
        )
        return clusters[:limit]
