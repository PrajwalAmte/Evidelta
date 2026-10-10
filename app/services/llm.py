from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import settings


class CitationVerifier:
    def __init__(self) -> None:
        self.strong_claim_patterns = (
            "definitely",
            "confirmed",
            "proven",
            "guaranteed",
            "certainly",
            "unequivocally",
        )

    def verify(
        self,
        *,
        summary: str,
        citations: list[str],
        evidence_ids: list[str] | None = None,
        attribution_state: str | None = None,
    ) -> bool:
        evidence_ids = evidence_ids or []
        if not isinstance(citations, list):
            return False
        if not citations:
            return False

        known = set(str(item) for item in evidence_ids)
        if known:
            for citation in citations:
                if str(citation) not in known:
                    return False

        if attribution_state == "provider_confirmed":
            return True

        lowered_summary = summary.lower()
        if any(term in lowered_summary for term in self.strong_claim_patterns):
            return False

        return True


class LLMSynthesizer:
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.provider = (settings.llm_provider or "ollama").lower()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.verifier = CitationVerifier()
        self.openrouter_api_key = settings.openrouter_api_key
        self.openrouter_base_url = (settings.openrouter_base_url or "https://openrouter.ai/api/v1").rstrip("/")
        self.openrouter_model = model or settings.openrouter_model or settings.ollama_model
        self.site_url = settings.openrouter_site_url
        self.site_name = settings.openrouter_site_name

    @property
    def active_model(self) -> str:
        return self.openrouter_model if self.provider == "openrouter" else self.model

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.provider == "openrouter" and self.openrouter_api_key:
            headers["Authorization"] = f"Bearer {self.openrouter_api_key}"
            if self.site_url:
                headers["HTTP-Referer"] = self.site_url
            if self.site_name:
                headers["X-OpenRouter-Title"] = self.site_name
        return headers

    def _parse_response_content(self, raw_content: Any) -> dict[str, Any]:
        if isinstance(raw_content, dict):
            parsed = raw_content
        else:
            try:
                parsed = json.loads(str(raw_content))
            except (TypeError, ValueError):
                return {"summary": str(raw_content), "citations": []}

        if not isinstance(parsed, dict):
            return {"summary": str(parsed), "citations": []}
        return parsed

    def _finalize_response(
        self,
        raw_content: Any,
        evidence_ids: list[str] | None,
        attribution_state: str | None,
    ) -> dict[str, Any]:
        parsed = self._parse_response_content(raw_content)
        summary = str(parsed.get("summary", ""))
        citations = parsed.get("citations", [])
        if not isinstance(citations, list):
            citations = [str(citations)] if citations else []
        normalized_citations = [str(item) for item in citations]
        valid = self.verifier.verify(
            summary=summary,
            citations=normalized_citations,
            evidence_ids=evidence_ids or [],
            attribution_state=attribution_state,
        )
        if not valid:
            return {
                "summary": "The synthesis output was rejected because it exceeded the available evidence or citation contract.",
                "citations": [],
            }
        return {"summary": summary, "citations": normalized_citations}

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        evidence_ids: list[str] | None = None,
        attribution_state: str | None = None,
    ) -> dict[str, Any]:
        sys_content = system_prompt or "You are a careful synthesis assistant. Return valid JSON with summary and citations."
        if self.provider == "openrouter":
            if not self.openrouter_api_key:
                return {
                    "summary": "Remote OpenRouter model is not configured. Set OPENROUTER_API_KEY to enable synthesis.",
                    "citations": [],
                    "available": False,
                }
            payload = {
                "model": self.openrouter_model,
                "messages": [
                    {"role": "system", "content": sys_content},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "max_tokens": 400,
            }
            try:
                response = httpx.post(
                    f"{self.openrouter_base_url}/chat/completions",
                    json=payload,
                    headers=self._build_headers(),
                    timeout=120.0,
                )
                response.raise_for_status()
            except (httpx.HTTPError, OSError):
                return {
                    "summary": "Remote OpenRouter synthesis is unavailable. The model endpoint is not responding.",
                    "citations": [],
                    "available": False,
                }
            content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "{}")
            return self._finalize_response(content, evidence_ids, attribution_state)

        # Ollama path kept for local development.
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_content},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }
        try:
            response = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=120.0)
            response.raise_for_status()
        except (httpx.HTTPError, OSError):
            return {
                "summary": "Local Ollama model unavailable. The synthesis layer is configured but the model endpoint is not responding.",
                "citations": [],
                "available": False,
            }
        content = response.json().get("message", {}).get("content", "{}")
        return self._finalize_response(content, evidence_ids, attribution_state)


# Backward-compatible alias so existing imports don't break during migration.
OllamaSynthesizer = LLMSynthesizer
