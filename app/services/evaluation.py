from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

ALLOWED_EPISODE_TYPES = {"acknowledged", "silent_confirmed", "control"}
BASELINE_NAME = "status_page_plus_manual_search"


def _to_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def replay_evidence_window(
    evidence: Sequence[Mapping[str, Any]] | Iterable[Mapping[str, Any]],
    *,
    cutoff: datetime | str | None = None,
) -> list[dict[str, Any]]:
    records = list(evidence)
    if cutoff is None:
        return [dict(record) for record in records]

    cutoff_dt = _to_datetime(cutoff)
    if cutoff_dt is None:
        return [dict(record) for record in records]

    replayed: list[dict[str, Any]] = []
    for record in records:
        observed_at = _to_datetime(record.get("observed_at"))
        if observed_at is None:
            continue
        if observed_at <= cutoff_dt:
            replayed.append(dict(record))
    return replayed


class EvaluationService:
    def evaluate(
        self,
        *,
        episodes: Sequence[Mapping[str, Any]],
        evidence: Sequence[Mapping[str, Any]],
        baseline: str = BASELINE_NAME,
    ) -> dict[str, Any]:
        normalized_episodes: list[dict[str, Any]] = []
        for episode in episodes:
            episode_type = str(episode.get("type") or "").strip()
            if episode_type not in ALLOWED_EPISODE_TYPES:
                raise ValueError(f"Unsupported episode type: {episode_type!r}")

            onset = _to_datetime(episode.get("onset"))
            ack = _to_datetime(episode.get("acknowledgment_time"))
            normalized_episodes.append(
                {
                    "episode_id": str(episode.get("episode_id") or "unknown-episode"),
                    "product": str(episode.get("product") or "unknown-product"),
                    "dimension": str(episode.get("dimension") or "unknown-dimension"),
                    "type": episode_type,
                    "onset": onset,
                    "acknowledgment_time": ack,
                }
            )

        confirmed_episodes = [ep for ep in normalized_episodes if ep["type"] != "control"]
        control_episodes = [ep for ep in normalized_episodes if ep["type"] == "control"]

        detected_metrics: list[dict[str, Any]] = []
        lead_times: list[float] = []

        for episode in normalized_episodes:
            matching = []
            for record in evidence:
                record_product = str(record.get("product") or "")
                record_dimension = str(record.get("dimension") or "")
                if record_product != episode["product"] or record_dimension != episode["dimension"]:
                    continue

                observed_at = _to_datetime(record.get("observed_at"))
                if observed_at is None:
                    continue
                if episode["onset"] is not None and observed_at < episode["onset"]:
                    continue
                if episode["acknowledgment_time"] is not None and observed_at > episode["acknowledgment_time"]:
                    continue
                matching.append(observed_at)

            if not matching:
                detected = False
                candidate_at = None
                lead_time_days = None
            else:
                detected = True
                candidate_at = min(matching)
                lead_time_days = self._lead_time_days(candidate_at, episode["acknowledgment_time"]) if episode["acknowledgment_time"] is not None else None
                if lead_time_days is not None:
                    lead_times.append(lead_time_days)

            detected_metrics.append(
                {
                    "episode_id": episode["episode_id"],
                    "product": episode["product"],
                    "dimension": episode["dimension"],
                    "type": episode["type"],
                    "detected": detected,
                    "candidate_at": candidate_at.isoformat() if candidate_at is not None else None,
                    "lead_time_days": lead_time_days,
                }
            )

        detected_confirmed = sum(
            1
            for entry in detected_metrics
            if entry["type"] != "control" and entry["detected"]
        )
        detected_controls = sum(
            1
            for entry in detected_metrics
            if entry["type"] == "control" and entry["detected"]
        )

        recall = (detected_confirmed / len(confirmed_episodes)) if confirmed_episodes else 0.0
        false_positive_rate = (detected_controls / len(control_episodes)) if control_episodes else 0.0
        mean_lead = sum(lead_times) / len(lead_times) if lead_times else 0.0

        return {
            "baseline": baseline,
            "episodes_total": len(normalized_episodes),
            "confirmed_episodes": len(confirmed_episodes),
            "controls_total": len(control_episodes),
            "detected_episodes": detected_confirmed,
            "recall": round(recall, 4),
            "false_positive_rate": round(false_positive_rate, 4),
            "mean_detection_lead_time_days": round(mean_lead, 4),
            "mean_diagnosis_time_days": round(mean_lead, 4),
            "episode_metrics": detected_metrics,
        }

    @staticmethod
    def _lead_time_days(detected_at: datetime, acknowledgment_time: datetime | None) -> float | None:
        if acknowledgment_time is None:
            return None
        delta = acknowledgment_time - detected_at
        return max(0.0, delta.total_seconds() / 86400.0)


__all__ = ["BASELINE_NAME", "EvaluationService", "replay_evidence_window"]
