from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.synthesis import SynthesisService

router = APIRouter(tags=["synthesis"])


class SynthesisRequest(BaseModel):
    cluster: dict[str, Any] = Field(default_factory=dict)


class ReplayValidationRequest(BaseModel):
    cases: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/synthesis/cluster")
async def synthesize_cluster(request: SynthesisRequest) -> dict[str, Any]:
    return SynthesisService().synthesize_cluster(request.cluster)


@router.post("/synthesis/replay-validation")
async def replay_validation(request: ReplayValidationRequest) -> dict[str, Any]:
    return SynthesisService().evaluate_historical_replay(cases=request.cases)
