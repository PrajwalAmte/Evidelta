from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.services.extraction import classify_report, resolve_dimension, resolve_product


class HackerNewsAdapter:
    def fetch_item(self, item_id: int) -> dict[str, Any]:
        response = httpx.get(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json", timeout=20.0)
        response.raise_for_status()
        payload = response.json()
        title = str(payload.get("title") or "")
        text = str(payload.get("text") or "")
        source_url = str(payload.get("url") or f"https://news.ycombinator.com/item?id={item_id}")
        classification = classify_report({"title": title, "body": text, "url": source_url, "source": "hackernews"})
        product_text = " ".join(part for part in [title, text] if part)
        return {
            "source_type": "hackernews",
            "source_url": source_url,
            "product": resolve_product(product_text) or "unknown",
            "dimension": resolve_dimension(product_text) or classification.get("dimension") or "unknown",
            "classification": classification,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "raw_content": {"title": title, "body": text, "item_id": item_id},
        }
