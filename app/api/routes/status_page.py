from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.ingestion import IngestionService
from app.services.status_page_adapter import StatusPageAdapter

router = APIRouter(tags=["status-page"])


class StatusPageRequest(BaseModel):
    incident_url: str = Field(..., min_length=1)


@router.post("/status-page/import")
async def import_status_page_incident(request: StatusPageRequest) -> dict[str, Any]:
    try:
        result = StatusPageAdapter().normalize_incident(request.incident_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    ingestion = IngestionService()
    observed_at = datetime.fromisoformat(str(result["observed_at"]).replace("Z", "+00:00"))
    evidence = ingestion.ingest_evidence(
        source_type=result["source_type"],
        source_url=result["source_url"],
        observed_at=observed_at,
        raw_content=result["raw_content"],
        author_id=result.get("provider_name"),
    )
    return {
        "status": "imported" if result["dimension"] != "unknown" else "insufficient_signal",
        "source_type": result["source_type"],
        "product": result["product"],
        "dimension": result["dimension"],
        "classification": result["classification"],
        "provider_name": result["provider_name"],
        "source_url": result["source_url"],
        "evidence": evidence,
    }
