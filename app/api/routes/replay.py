from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.replay import IssueReplayService

router = APIRouter(tags=["replay"])


class ReplayIssueRequest(BaseModel):
    issue_url: str = Field(..., min_length=1)


@router.post("/replay/issue")
async def replay_issue(request: ReplayIssueRequest) -> dict[str, Any]:
    service = IssueReplayService()
    try:
        return service.replay_issue(request.issue_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
