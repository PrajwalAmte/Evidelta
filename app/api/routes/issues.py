from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.issue_import import IssueImportPipeline

router = APIRouter(tags=["issues"])


class IssueImportRequest(BaseModel):
    issue_url: str = Field(..., min_length=1)


@router.post("/issues/import")
async def import_issue(request: IssueImportRequest) -> dict[str, Any]:
    pipeline = IssueImportPipeline()
    result = pipeline.import_issue(request.issue_url)
    if not result["classification"].get("is_change_report"):
        return {
            "status": "ignored",
            "reason": "Classifier did not identify this as a change report.",
            "product": result["product"],
            "dimension": result["dimension"],
            "classification": result["classification"],
        }

    return {
        "status": "imported",
        "source_type": result["source_type"],
        "product": result["product"],
        "dimension": result["dimension"],
        "classification": result["classification"],
        "evidence": result["evidence"],
    }
