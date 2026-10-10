from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.llm import LLMSynthesizer

router = APIRouter(tags=["llm"])


class SynthRequest(BaseModel):
    prompt: str
    system_prompt: str | None = None


class SynthResponse(BaseModel):
    summary: str
    citations: list[str]


@router.get("/llm/health")
async def llm_health() -> dict[str, str]:
    synthesizer = LLMSynthesizer()
    try:
        result = synthesizer.generate(prompt="Return JSON with summary and citations.", evidence_ids=[])
        if result.get("available") is False or not result.get("summary"):
            return {"status": "unavailable", "model": synthesizer.active_model}
        return {"status": "ok", "model": synthesizer.active_model}
    except Exception:
        return {"status": "unavailable", "model": synthesizer.active_model}


@router.post("/llm/synthesize", response_model=SynthResponse)
async def synthesize(request: SynthRequest) -> dict[str, Any]:
    synthesizer = LLMSynthesizer()
    return synthesizer.generate(prompt=request.prompt, system_prompt=request.system_prompt)


@router.get("/llm/model")
async def llm_model() -> dict[str, str]:
    synthesizer = LLMSynthesizer()
    return {"model": synthesizer.active_model}
