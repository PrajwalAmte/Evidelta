from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.models.evidence import EvidenceRecord, RawSnapshot
from app.services.evidence_pipeline import EvidencePipeline
from app.services.extraction import classify_report, resolve_dimension, resolve_product
from app.services.ingestion import IngestionService

router = APIRouter(tags=["ui"])


class ChangeFeedRequest(BaseModel):
    product: str = Field(default="all", min_length=1)
    limit: int = Field(default=10, ge=1, le=50)


class IncidentQueryRequest(BaseModel):
    product: str = Field(default="all", min_length=1)
    symptom: str = Field(default="observed change", min_length=1)
    time_window: str = Field(default="30d", min_length=1)


class EvidenceDetailsRequest(BaseModel):
    evidence_ids: list[str] = Field(default_factory=list)


@router.get("/ui/products")
async def ui_products() -> dict[str, Any]:
    pipeline = EvidencePipeline()
    records = pipeline._load_records(lookback_days=365)
    products = sorted({str(r["product"]) for r in records if r.get("product") and r["product"] != "unknown"})
    return {"products": products}


@router.post("/changes/feed")
async def change_feed(request: ChangeFeedRequest) -> dict[str, Any]:
    product_name = request.product if request.product != "all" else "all"
    pipeline = EvidencePipeline()
    changes = pipeline.build_candidate_changes(product=product_name, limit=request.limit)
    return {
        "product": product_name,
        "changes": changes,
        "status": "ready" if changes else "no_data",
        "message": "Candidate change records are synthesized from stored evidence and graded by evidence quality.",
    }


@router.post("/incident/query")
async def incident_query(request: IncidentQueryRequest) -> dict[str, Any]:
    product_name = request.product if request.product != "all" else "all"
    pipeline = EvidencePipeline()
    changes = pipeline.build_candidate_changes(product=product_name, limit=50)
    if not changes:
        return {
            "product": product_name,
            "symptom": request.symptom,
            "time_window": request.time_window,
            "summary": "No evidence-backed change records were found for this query window.",
            "evidence_ids": [],
            "status": "insufficient_evidence",
        }

    known = [item for item in changes if str(item.get("dimension")) != "unknown"]
    top = known[0] if known else changes[0]
    related = [
        item
        for item in changes
        if item.get("product") == top.get("product") and item.get("dimension") == top.get("dimension")
    ]
    source_families = sorted({str(item.get("provider") or "unknown") for item in related})
    total_evidence = sum(int(item.get("evidence_count", 0)) for item in related)
    total_independent = sum(int(item.get("independent_reports", 0)) for item in related)
    evidence_ids: list[str] = []
    for item in related:
        evidence_ids.extend([str(eid) for eid in item.get("evidence_ids", [])])
    # Preserve ordering while deduplicating IDs.
    seen: set[str] = set()
    ordered_ids: list[str] = []
    for evidence_id in evidence_ids:
        if evidence_id and evidence_id not in seen:
            seen.add(evidence_id)
            ordered_ids.append(evidence_id)

    summary = (
        f"{top['dimension']} signal for {top['product']} around {top['time_window']} is supported by "
        f"{total_independent} independent report(s) out of {total_evidence} evidence item(s) across "
        f"{len(source_families)} source family(ies) ({', '.join(source_families)}). "
        f"Attribution is {top['attribution_state']} with status {top['status']}."
    )
    return {
        "product": product_name,
        "symptom": request.symptom,
        "time_window": request.time_window,
        "summary": summary,
        "evidence_ids": ordered_ids,
        "status": top["status"],
    }


@router.post("/ui/evidence")
async def ui_evidence(request: EvidenceDetailsRequest) -> dict[str, Any]:
    if not request.evidence_ids:
        return {"evidence": []}

    service = IngestionService()
    with service.SessionLocal() as session:
        rows = session.execute(
            select(EvidenceRecord, RawSnapshot)
            .join(RawSnapshot, EvidenceRecord.snapshot_id == RawSnapshot.id)
            .where(EvidenceRecord.id.in_(request.evidence_ids))
        ).all()

    by_id = {row.id: row for row, _ in rows}
    evidence = []
    for evidence_id in request.evidence_ids:
        row = by_id.get(evidence_id)
        if row is None:
            continue
        raw_snapshot = next((snapshot for evidence_row, snapshot in rows if evidence_row.id == evidence_id), None)
        raw_payload = raw_snapshot.raw_payload if raw_snapshot is not None else "{}"
        try:
            payload = json.loads(raw_payload)
        except (TypeError, ValueError):
            payload = {"body": raw_payload}
        title = str(payload.get("title") or "")
        body = str(payload.get("body") or payload.get("content") or payload.get("message") or "")
        classification = classify_report({"title": title, "body": body, "url": row.source_url, "source": row.source_type})
        text = " ".join(part for part in [row.source_url, title, body] if part)
        product = resolve_product(text) or "unknown"
        dimension = resolve_dimension(text) or classification.get("dimension") or "unknown"
        evidence.append(
            {
                "id": row.id,
                "source_type": row.source_type,
                "source_url": row.source_url,
                "observed_at": row.observed_at.isoformat(),
                "fetched_at": row.fetched_at.isoformat(),
                "content_hash": row.content_hash,
                "snapshot_id": row.snapshot_id,
                "author_hash": row.author_hash,
                "raw_text": body or title,
                "product": product,
                "dimension": dimension,
                "classification": classification,
                "extraction": {
                    "product": product,
                    "dimension": dimension,
                    "matched_keywords": {
                        "product_matches": [
                            keyword
                            for keyword in [
                                "chat completions",
                                "chat-completions",
                                "openai",
                                "anthropic",
                                "gemini",
                                "claude",
                            ]
                            if keyword.lower() in text.lower()
                        ],
                        "dimension_matches": [
                            keyword
                            for key, keywords in {
                                "structured_output": [
                                    "structured output",
                                    "json schema",
                                    "schema validation",
                                    "response format",
                                    "json mode",
                                    "structured response",
                                ],
                                "rate_quota": ["rate limit", "quota", "429", "too many requests"],
                                "tool_calling": ["tool calling", "function calling"],
                                "refusal_behavior": ["refusal", "won't answer", "decline"],
                                "latency": ["latency", "slow", "response time"],
                                "availability": ["availability", "outage", "service unavailable"],
                            }.items()
                            for keyword in keywords
                            if keyword.lower() in text.lower() and (dimension == key or keyword.lower() in text.lower())
                        ],
                    },
                    "flags": {
                        "is_change_report": bool(classification.get("is_change_report")),
                        "first_hand": bool(classification.get("first_hand")),
                        "contains_reproducible_example": bool(classification.get("contains_reproducible_example")),
                        "direction": classification.get("direction", "unknown"),
                    },
                    "dimension": {"dimension": dimension, "reason": f"Matched keyword for '{dimension}' in the evidence text."},
                },
            }
        )
    return {"evidence": evidence}


@router.get("/ui", response_class=HTMLResponse)
async def ui_page() -> HTMLResponse:
    html = """
    <html>
      <head><title>Evidelta</title></head>
      <body>
        <h1>Evidelta</h1>
        <p>External Change Intelligence</p>
        <ul>
          <li>Change feed</li>
          <li>Incident query</li>
          <li>Evidence-backed synthesis</li>
        </ul>
      </body>
    </html>
    """
    return HTMLResponse(content=html)
