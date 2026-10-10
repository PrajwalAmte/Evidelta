from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from app.services.replay import IssueReplayService


class SynthesisService:
    def synthesize_cluster(self, cluster: Mapping[str, Any]) -> dict[str, Any]:
        records = list(cluster.get("records") or [])
        citations = [str(record.get("source_url") or "unknown") for record in records if record.get("source_url")]
        evidence_count = int(cluster.get("evidence_count") or len(records))
        independent_reports = int(cluster.get("independent_reports") or max(1, len(records)))
        attribution_state = str(cluster.get("attribution_state") or "insufficient_evidence")
        status = str(cluster.get("status") or "candidate")

        if attribution_state == "provider_confirmed":
            confidence = "high"
        elif attribution_state in {"temporally_associated", "observed_only"}:
            confidence = "medium" if evidence_count >= 2 else "low"
        else:
            confidence = "low"

        if evidence_count >= 3 and independent_reports >= 2:
            evidence_quality = "high"
        elif evidence_count >= 2:
            evidence_quality = "medium"
        else:
            evidence_quality = "low"

        summary = (
            f"A {cluster.get('dimension', 'unknown')} change signal for {cluster.get('product', 'unknown')} is supported by "
            f"{evidence_count} evidence item(s). The current attribution is {attribution_state}, and the signal remains "
            f"{status}. This is not a final claim beyond the available evidence."
        )

        return {
            "summary": summary,
            "citations": citations,
            "attribution_state": attribution_state,
            "confidence": confidence,
            "evidence_quality": evidence_quality,
            "status": status,
            "evidence_count": evidence_count,
            "independent_reports": independent_reports,
        }

    def evaluate_historical_replay(
        self,
        *,
        cases: Sequence[Mapping[str, Any]] | Iterable[Mapping[str, Any]],
    ) -> dict[str, Any]:
        replay_service = IssueReplayService()
        helpful = 0
        missed = 0
        overstated = 0
        insufficient_evidence_handled = 0
        total = 0

        for case in cases:
            total += 1
            issue_url = str(case.get("issue_url") or "")
            replay = replay_service.replay_issue(issue_url)
            expected_dimension = str(case.get("expected_dimension") or "")
            expected_product = str(case.get("expected_product") or "")

            product_match = replay["product"] == expected_product
            dimension_match = replay["dimension"] == expected_dimension

            if replay["status"] == "evidence_ready" and expected_dimension != "unknown" and product_match and dimension_match:
                helpful += 1
            elif replay["status"] == "insufficient_signal" and expected_dimension == "unknown" and product_match:
                insufficient_evidence_handled += 1

            if replay["status"] == "evidence_ready" and expected_dimension == "unknown":
                overstated += 1
            if replay["status"] == "insufficient_signal" and expected_dimension != "unknown":
                missed += 1

        return {
            "total_cases": total,
            "helpful_cases": helpful,
            "missed_cases": missed,
            "overstated_cases": overstated,
            "insufficient_evidence_handled": insufficient_evidence_handled,
            "summary": (
                "The replay is honest when it yields evidence-backed summaries and explicitly reports insufficient evidence "
                "without claiming measured or acknowledged status."
            ),
        }
