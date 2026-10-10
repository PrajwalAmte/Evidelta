from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.github_adapter import GitHubIssueAdapter
from app.services.ingestion import IngestionService


class IssueImportPipeline:
    def __init__(self) -> None:
        self.adapter = GitHubIssueAdapter()
        self.ingestion = IngestionService()

    def import_issue(self, issue_url: str) -> dict[str, Any]:
        issue = self.adapter.normalize_issue(issue_url)
        observed_at = datetime.fromisoformat(issue["observed_at"].replace("Z", "+00:00"))
        stored = self.ingestion.ingest_evidence(
            source_type=issue["source_type"],
            source_url=issue["source_url"],
            observed_at=observed_at,
            raw_content=issue["raw_content"],
            author_id=issue["raw_content"].get("author_login"),
        )
        result = {
            "source_type": issue["source_type"],
            "product": issue["product"],
            "dimension": issue["dimension"],
            "classification": issue["classification"],
            "evidence": stored,
        }
        return result
