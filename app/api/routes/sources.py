from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.docs_adapter import DocsAdapter
from app.services.hackernews_adapter import HackerNewsAdapter
from app.services.ingestion import IngestionService

router = APIRouter(tags=["sources"])


class HackerNewsImportRequest(BaseModel):
    item_id: int = Field(..., ge=1)


class DocsImportRequest(BaseModel):
    url: str = Field(..., min_length=1)


@router.post("/sources/hackernews/import")
async def import_hackernews(request: HackerNewsImportRequest) -> dict[str, Any]:
    adapter = HackerNewsAdapter()
    ingestion = IngestionService()
    try:
        item = adapter.fetch_item(request.item_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch Hacker News item: {exc}") from exc
    observed_at = datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00"))
    evidence = ingestion.ingest_evidence(
        source_type=item["source_type"],
        source_url=item["source_url"],
        observed_at=observed_at,
        raw_content=item["raw_content"],
    )
    return {
        "status": "imported" if item["dimension"] != "unknown" else "insufficient_signal",
        "source_type": item["source_type"],
        "product": item["product"],
        "dimension": item["dimension"],
        "classification": item["classification"],
        "evidence": evidence,
    }


@router.post("/sources/docs/import")
async def import_docs(request: DocsImportRequest) -> dict[str, Any]:
    adapter = DocsAdapter()
    ingestion = IngestionService()
    try:
        doc = adapter.fetch_doc(request.url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch doc URL: {exc}") from exc
    observed_at = datetime.fromisoformat(doc["observed_at"].replace("Z", "+00:00"))
    evidence = ingestion.ingest_evidence(
        source_type=doc["source_type"],
        source_url=doc["source_url"],
        observed_at=observed_at,
        raw_content=doc["raw_content"],
    )
    return {
        "status": "imported" if doc["dimension"] != "unknown" else "insufficient_signal",
        "source_type": doc["source_type"],
        "product": doc["product"],
        "dimension": doc["dimension"],
        "classification": doc["classification"],
        "evidence": evidence,
    }
