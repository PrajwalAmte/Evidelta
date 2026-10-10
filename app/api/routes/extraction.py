from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.extraction import classify_report, resolve_dimension, resolve_product

router = APIRouter(tags=["extraction"])


class ExtractionRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    url: str | None = None
    source: str | None = None


class ExtractionResponse(BaseModel):
    product: str | None
    dimension: str | None
    classification: dict[str, Any]


@router.post("/extract", response_model=ExtractionResponse)
async def extract_report(request: ExtractionRequest) -> dict[str, Any]:
    text = " ".join(part for part in [request.title, request.body] if part)
    return {
        "product": resolve_product(text),
        "dimension": resolve_dimension(text),
        "classification": classify_report({
            "title": request.title,
            "body": request.body,
            "url": request.url,
            "source": request.source,
        }),
    }
