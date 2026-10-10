from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from app.services.extraction import classify_report, resolve_dimension, resolve_product

_PLACEHOLDER_INCIDENT_RE = re.compile(r"^(?:abc|abc123|xyz|test|demo|fixture|placeholder|final-check|final_check)[\w-]*$", re.IGNORECASE)


class StatusPageAdapter:
    def __init__(self, base_url: str = "https://status.openai.com") -> None:
        self.base_url = base_url.rstrip("/")

    def _incident_url(self, incident_url: str) -> str:
        parsed = urlparse(incident_url)
        if not parsed.netloc:
            raise ValueError(f"Unsupported status page URL: {incident_url}")
        incident_id = parsed.path.rstrip("/").split("/")[-1]
        if not incident_id or _PLACEHOLDER_INCIDENT_RE.fullmatch(incident_id):
            raise ValueError(
                f"Placeholder status incident URL rejected: {incident_url}. Use a real provider status incident URL."
            )
        return incident_url

    def fetch_incident(self, incident_url: str) -> dict[str, Any]:
        url = self._incident_url(incident_url)
        response = httpx.get(url, timeout=20.0, headers={"User-Agent": "Evidelta-status-adapter"})
        response.raise_for_status()
        html = response.text or ""
        title_match = ""
        try:
            title_match = html.split("<title>", 1)[1].split("</title>", 1)[0]
        except IndexError:
            title_match = ""
        description = ""
        for marker in ("meta name='description'", 'meta property="og:description"', 'meta name="description"'):
            if marker in html:
                start = html.index(marker)
                snippet = html[start:]
                content_start = snippet.find("content=")
                if content_start != -1:
                    after = snippet[content_start + len("content="):]
                    if after.startswith('"'):
                        description = after.split('"', 1)[1]
                    elif after.startswith("'"):
                        description = after.split("'", 1)[1]
                    break
        text = " ".join(part for part in [title_match, description, html] if part)
        classification = classify_report({"title": title_match, "body": description, "url": incident_url, "source": "status_page"})
        product = resolve_product(text) or "unknown"
        dimension = resolve_dimension(text) or classification.get("dimension") or "unknown"
        provider_name = "openai" if "openai" in text.lower() else "provider"
        return {
            "source_type": "status_page",
            "provider_name": provider_name,
            "product": product,
            "dimension": dimension,
            "classification": classification,
            "title": title_match,
            "body": description,
            "source_url": incident_url,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }

    def normalize_incident(self, incident_url: str) -> dict[str, Any]:
        data = self.fetch_incident(incident_url)
        return {
            "source_type": data["source_type"],
            "source_url": data["source_url"],
            "observed_at": data["observed_at"],
            "product": data["product"],
            "dimension": data["dimension"],
            "classification": data["classification"],
            "provider_name": data["provider_name"],
            "raw_content": {
                "title": data["title"],
                "body": data["body"],
            },
        }
