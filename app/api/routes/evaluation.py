from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.evaluation import EvaluationService

router = APIRouter(tags=["evaluation"])


class EvaluationRequest(BaseModel):
    episodes: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    baseline: str = "status_page_plus_manual_search"


@router.post("/evaluation/run")
async def run_evaluation(request: EvaluationRequest) -> dict[str, Any]:
    return EvaluationService().evaluate(
        episodes=request.episodes,
        evidence=request.evidence,
        baseline=request.baseline,
    )
