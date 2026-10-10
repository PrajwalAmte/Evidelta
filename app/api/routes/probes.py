from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.ingestion import IngestionService
from app.services.probe_runner import ProbeRunner

router = APIRouter(tags=["probes"])


class ProbeRequest(BaseModel):
    provider: str = Field(..., min_length=1)
    product: str = Field(..., min_length=1)
    dimension: str = Field(..., min_length=1)
    region: str = "us-east-1"
    account_tier: str = "standard"
    headers: dict[str, Any] = Field(default_factory=dict)
    tool_results: list[bool] | None = None
    structured_outputs: list[bool] | None = None
    refusal_responses: list[str] | None = None
    latencies_ms: list[float] | None = None
    error_rate: float | None = None


@router.post("/probes/run")
async def run_probe(request: ProbeRequest) -> dict[str, Any]:
    runner = ProbeRunner(region=request.region, account_tier=request.account_tier)
    return runner.run_probe(
        provider=request.provider,
        product=request.product,
        dimension=request.dimension,
        headers=request.headers,
        tool_results=request.tool_results,
        structured_outputs=request.structured_outputs,
        refusal_responses=request.refusal_responses,
        latencies_ms=request.latencies_ms,
        error_rate=request.error_rate,
    )


@router.post("/probes/run-suite")
async def run_probe_suite(request: ProbeRequest) -> dict[str, dict[str, Any]]:
    runner = ProbeRunner(region=request.region, account_tier=request.account_tier)
    return runner.run_suite(
        provider=request.provider,
        product=request.product,
        rate_headers=request.headers,
        tool_results=request.tool_results,
        structured_outputs=request.structured_outputs,
        refusal_responses=request.refusal_responses,
        latencies_ms=request.latencies_ms,
        error_rate=request.error_rate,
    )


@router.post("/probes/ingest")
async def run_and_ingest_probe(request: ProbeRequest) -> dict[str, Any]:
    runner = ProbeRunner(region=request.region, account_tier=request.account_tier)
    result = runner.run_probe(
        provider=request.provider,
        product=request.product,
        dimension=request.dimension,
        headers=request.headers,
        tool_results=request.tool_results,
        structured_outputs=request.structured_outputs,
        refusal_responses=request.refusal_responses,
        latencies_ms=request.latencies_ms,
        error_rate=request.error_rate,
    )

    product_path = request.product
    if product_path.startswith(f"{request.provider}/"):
        product_path = product_path[len(request.provider) + 1 :]

    raw_content = {
        "title": f"Probe result for {request.product} {request.dimension}",
        "body": f"Probe status={result['status']} success_rate={result['success_rate']}",
        "probe": result,
        # A stable probe indicates no reproduced issue; degraded/elevated outcomes indicate reproduction.
        "measurement_reproduced": result.get("status") in {"watch", "degraded", "critical", "elevated"},
    }
    ingestion = IngestionService()
    observed_at = datetime.fromisoformat(str(result["observed_at"]).replace("Z", "+00:00"))
    evidence = ingestion.ingest_evidence(
        source_type="probe",
        source_url=f"probe://{request.provider}/{product_path}/{request.dimension}",
        observed_at=observed_at,
        raw_content=raw_content,
    )
    return {
        "probe": result,
        "evidence": evidence,
        "status": "ingested",
    }
