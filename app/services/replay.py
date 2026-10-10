from __future__ import annotations

from typing import Any

from app.services.github_adapter import GitHubIssueAdapter


class IssueReplayService:
    def __init__(self, adapter: GitHubIssueAdapter | None = None) -> None:
        self.adapter = adapter or GitHubIssueAdapter()

    @staticmethod
    def _signal_score(classification: dict[str, Any], *, product: str, dimension: str) -> float:
        score = 0.0
        if classification.get("is_change_report"):
            score += 0.4
        if dimension and dimension != "unknown":
            score += 0.25
        if product and product != "unknown":
            score += 0.15
        if classification.get("first_hand"):
            score += 0.1
        if classification.get("contains_reproducible_example"):
            score += 0.1
        return round(min(score, 1.0), 2)

    def replay_issue(self, issue_url: str) -> dict[str, Any]:
        issue = self.adapter.normalize_issue(issue_url)
        classification = issue["classification"]
        product = issue["product"]
        dimension = issue["dimension"]
        signal_score = self._signal_score(classification, product=product, dimension=dimension)
        should_cluster = bool(
            issue["source_type"] == "github"
            and product not in (None, "unknown")
            and dimension not in (None, "unknown")
            and signal_score >= 0.7
        )
        return {
            "source_type": issue["source_type"],
            "source_url": issue["source_url"],
            "product": product,
            "dimension": dimension,
            "classification": classification,
            "signal_score": signal_score,
            "should_cluster": should_cluster,
            "status": "evidence_ready" if should_cluster else "insufficient_signal",
            "next_action": (
                "Add a status-page adapter and baseline-aware clustering only after this issue clears the evidence threshold."
                if should_cluster
                else "Collect more supporting evidence before clustering; this issue is not strong enough yet."
            ),
            "evidence": {
                "source_url": issue["source_url"],
                "product": product,
                "dimension": dimension,
                "classification": classification,
            },
        }
