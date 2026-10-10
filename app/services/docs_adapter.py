from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.services.extraction import classify_report, resolve_dimension, resolve_product


class DocsAdapter:
    def fetch_doc(self, url: str) -> dict[str, Any]:
        response = httpx.get(url, timeout=20.0, headers={"User-Agent": "Evidelta-docs-adapter"})
        response.raise_for_status()
        text = response.text or ""
        title = ""
        if "<title>" in text and "</title>" in text:
            title = text.split("<title>", 1)[1].split("</title>", 1)[0]
        body = text[:4000]
        classification = classify_report({"title": title, "body": body, "url": url, "source": "docs"})
        product_text = " ".join(part for part in [title, body] if part)
        return {
            "source_type": "docs",
            "source_url": url,
            "product": resolve_product(product_text) or "unknown",
            "dimension": resolve_dimension(product_text) or classification.get("dimension") or "unknown",
            "classification": classification,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "raw_content": {"title": title, "body": text[:10000]},
        }
