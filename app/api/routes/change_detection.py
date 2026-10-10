from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.change_detection import cluster_evidence, grade_evidence

router = APIRouter(tags=["change-detection"])


class GradeRequest(BaseModel):
    volume: Literal["low", "medium", "high"]
    independence: Literal["low", "medium", "high"]
    reproducibility: Literal["none", "partial", "shared_prompt_output_examples"]
    measurement: Literal["not_testable", "not_reproduced", "reproduced"]
    provider_confirmation: Literal["none", "doc_change", "acknowledged"]
    recency: Literal["stale", "recent", "ongoing"]
    evidence_count: int = Field(default=1, ge=1)
    families: int = Field(default=1, ge=1)


class ClusterRequest(BaseModel):
    records: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/change/grade")
async def grade_change(request: GradeRequest) -> dict[str, Any]:
    return grade_evidence(
        volume=request.volume,
        independence=request.independence,
        reproducibility=request.reproducibility,
        measurement=request.measurement,
        provider_confirmation=request.provider_confirmation,
        recency=request.recency,
        evidence_count=request.evidence_count,
        families=request.families,
    )


@router.post("/change/cluster")
async def cluster_changes(request: ClusterRequest) -> dict[str, Any]:
    clusters = cluster_evidence(request.records)
    return {
        "cluster_count": len(clusters),
        "clusters": clusters,
        "status": "candidate_records_ready" if clusters else "no_candidate_records",
    }
