from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

VOLUME_SCORES: dict[str, int] = {"low": 1, "medium": 2, "high": 3}
INDEPENDENCE_SCORES: dict[str, int] = {"low": 1, "medium": 2, "high": 3}
REPRODUCIBILITY_SCORES: dict[str, int] = {"none": 0, "partial": 1, "shared_prompt_output_examples": 2}
MEASUREMENT_SCORES: dict[str, int] = {"not_testable": 0, "not_reproduced": 1, "reproduced": 2}
PROVIDER_SCORES: dict[str, int] = {"none": 0, "doc_change": 1, "acknowledged": 2}
RECENCY_SCORES: dict[str, int] = {"stale": 0, "recent": 1, "ongoing": 2}


@dataclass(frozen=True)
class ConditionSet:
    version: str = "2026.10"
    rules: Mapping[str, Any] = field(
        default_factory=lambda: {
            "status_priority": {
                "candidate": 0,
                "corroborated": 1,
                "measured": 2,
                "acknowledged": 3,
            },
            "attribution_state": {
                "observed_only": "observed_only",
                "temporally_associated": "temporally_associated",
                "provider_confirmed": "provider_confirmed",
                "insufficient_evidence": "insufficient_evidence",
            },
        }
    )


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _time_window_for(record: Mapping[str, Any]) -> str:
    observed_at = _parse_datetime(record.get("observed_at"))
    if observed_at is None:
        return "unknown"
    return observed_at.strftime("%Y-%m-%d")


def _dedupe_key(record: Mapping[str, Any]) -> tuple[str, str, str, str]:
    provider = str(record.get("provider") or record.get("source_type") or "unknown")
    product = str(record.get("product") or "unknown")
    dimension = str(record.get("dimension") or record.get("classification", {}).get("dimension") or "unknown")
    signature = " ".join(
        str(record.get(field, ""))
        for field in ("source_url", "title", "body", "summary", "content", "message")
    ).strip().lower()
    return provider, product, dimension, signature


def summarize_status(*, evidence_count: int, families: int, measurement_observed: bool, provider_confirmed: bool, valid_measurement: bool = True) -> str:
    if provider_confirmed and measurement_observed and valid_measurement:
        return "acknowledged"
    if measurement_observed and valid_measurement:
        return "measured"
    if families >= 2 and evidence_count >= 2:
        return "corroborated"
    return "candidate"


def summarize_attribution_state(
    *,
    score: int,
    provider_confirmation: str,
    measurement: str,
    independent_reports: int,
) -> str:
    if provider_confirmation == "acknowledged" and measurement == "reproduced":
        return "provider_confirmed"
    if provider_confirmation == "acknowledged":
        return "temporally_associated"
    if independent_reports >= 2 and score >= 3:
        return "observed_only"
    if score >= 7:
        return "temporally_associated"
    if score >= 3:
        return "observed_only"
    return "insufficient_evidence"


def evidence_grade_score(
    *,
    volume: str,
    independence: str,
    reproducibility: str,
    measurement: str,
    provider_confirmation: str,
    recency: str,
) -> tuple[int, str, str]:
    volume_score = VOLUME_SCORES[volume]
    independence_score = INDEPENDENCE_SCORES[independence]
    reproducibility_score = REPRODUCIBILITY_SCORES[reproducibility]
    measurement_score = MEASUREMENT_SCORES[measurement]
    provider_score = PROVIDER_SCORES[provider_confirmation]
    recency_score = RECENCY_SCORES[recency]

    score = volume_score + independence_score + reproducibility_score + measurement_score + provider_score + recency_score
    if score >= 9:
        label = "high"
    elif score >= 6:
        label = "medium"
    else:
        label = "low"
    # Default attribution for backward compatibility when standalone grade scoring is used.
    attribution = "temporally_associated" if score >= 7 else "observed_only" if score >= 3 else "insufficient_evidence"
    return score, label, attribution


def grade_evidence(
    *,
    volume: str,
    independence: str,
    reproducibility: str,
    measurement: str,
    provider_confirmation: str,
    recency: str,
    evidence_count: int = 1,
    families: int = 1,
    independent_reports: int | None = None,
) -> dict[str, Any]:
    score, grade, attribution_state = evidence_grade_score(
        volume=volume,
        independence=independence,
        reproducibility=reproducibility,
        measurement=measurement,
        provider_confirmation=provider_confirmation,
        recency=recency,
    )
    inferred_independent = independent_reports if independent_reports is not None else max(1, evidence_count)
    attribution_state = summarize_attribution_state(
        score=score,
        provider_confirmation=provider_confirmation,
        measurement=measurement,
        independent_reports=inferred_independent,
    )
    status = summarize_status(
        evidence_count=evidence_count,
        families=families,
        measurement_observed=measurement == "reproduced",
        provider_confirmed=attribution_state == "provider_confirmed",
    )
    return {
        "score": score,
        "grade": grade,
        "status": status,
        "attribution_state": attribution_state,
        "summary": f"Evidence quality is {grade} with a status of {status}.",
        "rubric_version": ConditionSet().version,
    }


def cluster_evidence(records: Sequence[Mapping[str, Any]] | Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[Mapping[str, Any]]] = {}
    for record in records:
        provider = str(record.get("provider") or record.get("source_type") or "unknown")
        product = str(record.get("product") or "unknown")
        classification = record.get("classification") or {}
        dimension = str(record.get("dimension") or classification.get("dimension") or "unknown")
        time_window = _time_window_for(record)
        key = (provider, product, dimension, time_window)
        grouped.setdefault(key, []).append(record)

    clusters: list[dict[str, Any]] = []
    for (provider, product, dimension, time_window), items in sorted(grouped.items(), key=lambda x: x[0]):
        deduped: list[Mapping[str, Any]] = []
        seen: set[tuple[str, str, str, str]] = set()
        seen_hashes: set[str] = set()
        for item in items:
            content_hash = str(item.get("content_hash") or "")
            if content_hash and content_hash in seen_hashes:
                continue
            key_value = _dedupe_key(item)
            if key_value in seen:
                continue
            seen.add(key_value)
            if content_hash:
                seen_hashes.add(content_hash)
            deduped.append(item)

        evidence_count = len(deduped)
        duplicate_count = max(0, len(items) - evidence_count)
        distinct_authors = {
            str(item.get("author_hash") or "unknown")
            for item in deduped
            if item.get("author_hash") is not None
        }
        distinct_source_urls = {str(item.get("source_url") or "unknown") for item in deduped}
        independent_reports = max(1, len(distinct_authors) if distinct_authors else min(evidence_count, 1))
        if len(distinct_source_urls) > independent_reports:
            independent_reports = max(1, min(evidence_count, len(distinct_source_urls)))
        first_hand_count = sum(1 for item in deduped if bool((item.get("classification") or {}).get("first_hand")))
        hearsay_count = evidence_count - first_hand_count
        reproduced_count = sum(1 for item in deduped if bool((item.get("classification") or {}).get("measurement_reproduced")))
        reproducible_example_count = sum(1 for item in deduped if bool((item.get("classification") or {}).get("contains_reproducible_example")))
        not_reproduced_count = evidence_count - reproduced_count
        valid_measurement = product != "unknown" and dimension != "unknown" and reproduced_count >= 1
        provider_acknowledged = any(
            str(item.get("provider") or item.get("source_type") or "").lower() in {"status_page", "official", "provider"}
            or bool((item.get("classification") or {}).get("provider_acknowledged"))
            for item in deduped
        )

        observed_times = [_parse_datetime(item.get("observed_at")) for item in deduped if _parse_datetime(item.get("observed_at")) is not None]
        recency = "ongoing" if observed_times and max(observed_times) >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) else "recent" if observed_times else "stale"

        volume = "high" if evidence_count >= 3 else "medium" if evidence_count >= 2 else "low"
        independence = "high" if independent_reports >= 2 else "medium" if evidence_count >= 2 else "low"
        reproducibility = "shared_prompt_output_examples" if reproducible_example_count >= 2 else "partial" if reproducible_example_count >= 1 else "none"
        measurement = "reproduced" if valid_measurement else "not_reproduced"
        provider_confirmation = "acknowledged" if provider_acknowledged else "none"
        grade = grade_evidence(
            volume=volume,
            independence=independence,
            reproducibility=reproducibility,
            measurement=measurement,
            provider_confirmation=provider_confirmation,
            recency=recency,
            evidence_count=evidence_count,
            families=1,
            independent_reports=independent_reports,
        )
        clusters.append(
            {
                "cluster_id": f"{provider}:{product}:{dimension}:{time_window}",
                "provider": provider,
                "product": product,
                "dimension": dimension,
                "time_window": time_window,
                "evidence_count": evidence_count,
                "independent_reports": independent_reports,
                "duplicates": duplicate_count,
                "first_hand_reports": first_hand_count,
                "hearsay_reports": hearsay_count,
                "reproduced_reports": reproduced_count,
                "not_reproduced_reports": not_reproduced_count,
                "provider_acknowledged": provider_acknowledged,
                "recency": recency,
                "status": grade["status"],
                "grade": grade["grade"],
                "attribution_state": grade["attribution_state"],
                "summary": grade["summary"],
                "evidence_ids": [str(item.get("evidence_id") or item.get("id") or "") for item in deduped if item.get("evidence_id") or item.get("id")],
                "records": deduped,
            }
        )

    return clusters


__all__ = [
    "ConditionSet",
    "cluster_evidence",
    "evidence_grade_score",
    "grade_evidence",
    "summarize_attribution_state",
    "summarize_status",
]
