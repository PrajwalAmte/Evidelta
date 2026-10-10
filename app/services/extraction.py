from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Mapping, Sequence

PRODUCT_ALIASES = {
    "openai/responses-api": [
        "responses api",
        "responses-api",
        "response format",
        "responsesapi",
    ],
    "openai/chat-completions": [
        "chat completions",
        "chat-completions",
        "gpt-4o",
        "chatgpt",
    ],
    "anthropic/claude": [
        "claude",
        "anthropic",
        "messages api",
    ],
    "google/gemini": [
        "gemini",
        "google ai",
        "generative ai",
    ],
    "openai": [
        "openai",
    ],
}

DIMENSION_KEYWORDS = {
    "structured_output": [
        "structured output",
        "json schema",
        "schema validation",
        "response format",
        "json mode",
        "structured response",
    ],
    "rate_quota": [
        "rate limit",
        "quota",
        "rate-limit",
        "429",
        "too many requests",
        "ratelimit",
        "daily limit",
    ],
    "tool_calling": [
        "tool calling",
        "tool call",
        "function calling",
        "tool invocation",
        "tool call failed",
        "function calling broken",
    ],
    "refusal_behavior": [
        "refusal",
        "refusing",
        "won't answer",
        "decline",
        "safety policy",
        "sudden refusal",
    ],
    "latency": [
        "latency",
        "slow",
        "ttft",
        "response time",
        "time to first token",
    ],
    "availability": [
        "availability",
        "down",
        "error rate",
        "outage",
        "503",
        "service unavailable",
    ],
}

_FIRST_PERSON_RE = re.compile(r"\b(i|we|our|me|my|team)\b", re.IGNORECASE)
_HEARSAY_RE = re.compile(r"\b(heard|people say|apparently|someone said)\b", re.IGNORECASE)
_WORSE_FLAGS = ("broke", "failed", "regressed", "dropped", "worse", "degraded")
_BETTER_FLAGS = ("fixed", "improved", "better", "recovered")


def _classify_direction(text: str) -> str:
    if any(flag in text for flag in _WORSE_FLAGS):
        return "worse"
    if any(flag in text for flag in _BETTER_FLAGS):
        return "better"
    return "changed"


def _text_with_url(report: Mapping[str, Any]) -> str:
    fields = ["title", "body", "content", "summary", "message", "url", "source"]
    return " ".join(str(report.get(field, "")) for field in fields).lower()


def classify_report(report: Mapping[str, Any]) -> dict[str, Any]:
    text = _text_with_url(report)

    if not text.strip():
        return {
            "is_change_report": False,
            "dimension": None,
            "direction": "unknown",
            "first_hand": False,
            "contains_reproducible_example": False,
        }

    dimension = resolve_dimension(text)
    direction = _classify_direction(text)
    first_hand = bool(_FIRST_PERSON_RE.search(text)) and not bool(_HEARSAY_RE.search(text))
    contains_reproducible_example = bool(re.search(r"(example|repro|prompt|schema|json|payload|request|response)", text))

    return {
        "is_change_report": bool(dimension) or any(flag in text for flag in ["broke", "failed", "regressed", "changed", "degraded", "suddenly"]),
        "dimension": dimension,
        "direction": direction,
        "first_hand": first_hand,
        "contains_reproducible_example": contains_reproducible_example,
    }


def resolve_product(text: str, alias_table: Mapping[str, Sequence[str]] | None = None) -> str | None:
    alias_map = alias_table or PRODUCT_ALIASES
    normalized = text.lower()

    if "responses api" in normalized or "responses-api" in normalized:
        return "openai/responses-api"
    if "chat completions" in normalized or "chat-completions" in normalized:
        return "openai/chat-completions"
    if "claude" in normalized or "anthropic" in normalized:
        return "anthropic/claude"
    if "gemini" in normalized or "google ai" in normalized or "generative ai" in normalized:
        return "google/gemini"

    for canonical, aliases in alias_map.items():
        for alias in aliases:
            if alias.lower() in normalized and canonical != "openai":
                return canonical

    if "openai" in normalized:
        return "openai"
    if "github.com/openai/" in normalized:
        return "openai"
    if "github.com/anthropic/" in normalized:
        return "anthropic/claude"
    if "github.com/google/" in normalized:
        return "google/gemini"
    return None


def resolve_dimension(text: str, dimension_keywords: Mapping[str, Sequence[str]] | None = None) -> str | None:
    keywords_map = dimension_keywords or DIMENSION_KEYWORDS
    normalized = text.lower()
    for dimension, keywords in keywords_map.items():
        for keyword in keywords:
            if keyword.lower() in normalized:
                return dimension
    return None


def deduplicate_reports(records: Sequence[Mapping[str, Any]]) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    deduped: list[Mapping[str, Any]] = []
    duplicates: list[Mapping[str, Any]] = []
    seen: list[Mapping[str, Any]] = []

    for record in records:
        payload = " ".join(
            str(record.get(field, ""))
            for field in ("title", "body", "content", "url")
        ).lower().strip()
        is_duplicate = False
        for existing in seen:
            existing_payload = " ".join(
                str(existing.get(field, ""))
                for field in ("title", "body", "content", "url")
            ).lower().strip()
            score = SequenceMatcher(None, payload, existing_payload).ratio()
            if payload and existing_payload and score >= 0.90:
                is_duplicate = True
                duplicates.append(record)
                break
        if not is_duplicate:
            deduped.append(record)
            seen.append(record)

    return deduped, duplicates


def calculate_effective_count(raw_count: int, concentration: float) -> float:
    if raw_count <= 0:
        return 0.0
    normalized = max(0.0, min(1.0, concentration))
    return raw_count * (1.0 - (0.6 * normalized))


def independence_metrics(raw_count: int, duplicates: Sequence[Mapping[str, Any]] | None = None) -> dict[str, float]:
    duplicate_count = len(duplicates or [])
    concentration = min(1.0, duplicate_count / max(raw_count, 1))
    effective_count = calculate_effective_count(raw_count, concentration)
    return {
        "raw_count": float(raw_count),
        "effective_count": float(effective_count),
        "concentration": float(concentration),
    }
