from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from app.services.extraction import classify_report, resolve_dimension, resolve_product


class GitHubIssueAdapter:
    def __init__(self, api_base: str = "https://api.github.com") -> None:
        self.api_base = api_base.rstrip("/")

    def _issue_api_url(self, issue_url: str) -> str:
        parsed = urlparse(issue_url)
        path_parts = [part for part in parsed.path.strip("/").split("/") if part]
        if len(path_parts) < 4:
            raise ValueError(f"Unsupported GitHub issue URL: {issue_url}")
        repo_path = "/".join(path_parts[:-2])
        issue_number = path_parts[-1]
        return f"{self.api_base}/repos/{repo_path}/issues/{issue_number}"

    def fetch_issue(self, issue_url: str) -> dict[str, Any]:
        api_url = self._issue_api_url(issue_url)
        response = httpx.get(api_url, timeout=20.0, headers={"Accept": "application/vnd.github+json"})
        response.raise_for_status()
        payload = response.json()
        title = str(payload.get("title") or "")
        body = str(payload.get("body") or "")
        text = " ".join(part for part in [issue_url, title, body] if part)
        classification = classify_report({"title": title, "body": body, "url": issue_url, "source": "github"})
        return {
            "source_type": "github",
            "product": resolve_product(text) or "unknown",
            "dimension": resolve_dimension(text) or "unknown",
            "classification": classification,
            "title": title,
            "body": body,
            "issue_number": api_url.rsplit("/", 1)[-1],
            "source_url": issue_url,
            "observed_at": payload.get("updated_at") or datetime.now(timezone.utc).isoformat(),
            "author_login": payload.get("user", {}).get("login"),
        }

    def normalize_issue(self, issue_url: str) -> dict[str, Any]:
        data = self.fetch_issue(issue_url)
        return {
            "source_type": data["source_type"],
            "source_url": data["source_url"],
            "observed_at": data["observed_at"],
            "product": data["product"],
            "dimension": data["dimension"],
            "classification": data["classification"],
            "raw_content": {
                "title": data["title"],
                "body": data["body"],
                "author_login": data["author_login"],
            },
        }
