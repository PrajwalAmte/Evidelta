from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.services.ingestion import IngestionService

router = APIRouter(tags=["ingestion"])


def _get_ingestion_service() -> IngestionService:
    return IngestionService()


class IngestEvidenceRequest(BaseModel):
    source_type: str = Field(..., min_length=1)
    source_url: str = Field(..., min_length=1)
    observed_at: datetime
    raw_content: str | dict
    author_id: str | None = None


@router.post("/ingest")
async def ingest_evidence(
    request: IngestEvidenceRequest,
    service: IngestionService = Depends(_get_ingestion_service),
) -> dict:
    return service.ingest_evidence(
        source_type=request.source_type,
        source_url=request.source_url,
        observed_at=request.observed_at,
        raw_content=request.raw_content,
        author_id=request.author_id,
    )


@router.get("/replay")
async def replay_evidence(
    cutoff: datetime = Query(...),
    service: IngestionService = Depends(_get_ingestion_service),
) -> list[dict]:
    return service.replay_as_of(cutoff)
