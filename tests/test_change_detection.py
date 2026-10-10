from app.services.change_detection import (
    ConditionSet,
    cluster_evidence,
    grade_evidence,
    summarize_attribution_state,
    summarize_status,
)


def test_cluster_evidence_builds_candidate_changes_from_noisy_signals() -> None:
    records = [
        {
            "provider": "github",
            "source_url": "https://github.com/openai/openai-python/pull/2733",
            "observed_at": "2026-10-08T09:00:00Z",
            "product": "openai/chat-completions",
            "dimension": "structured_output",
            "classification": {
                "is_change_report": True,
                "dimension": "structured_output",
                "direction": "changed",
                "first_hand": True,
                "contains_reproducible_example": True,
            },
        },
        {
            "provider": "github",
            "source_url": "https://github.com/openai/openai-python/issues/4023",
            "observed_at": "2026-10-08T09:15:00Z",
            "product": "openai/chat-completions",
            "dimension": "structured_output",
            "classification": {
                "is_change_report": True,
                "dimension": "structured_output",
                "direction": "changed",
                "first_hand": True,
                "contains_reproducible_example": True,
            },
        },
        {
            "provider": "status_page",
            "source_url": "https://status.openai.com/incidents/abc",
            "observed_at": "2026-10-08T10:00:00Z",
            "product": "openai/chat-completions",
            "dimension": "structured_output",
            "classification": {
                "is_change_report": True,
                "dimension": "structured_output",
                "direction": "changed",
                "first_hand": False,
                "contains_reproducible_example": False,
            },
        },
    ]

    clusters = cluster_evidence(records)

    assert len(clusters) == 2
    providers = {cluster["provider"] for cluster in clusters}
    assert providers == {"github", "status_page"}

    github_cluster = next(cluster for cluster in clusters if cluster["provider"] == "github")
    status_cluster = next(cluster for cluster in clusters if cluster["provider"] == "status_page")

    assert github_cluster["product"] == "openai/chat-completions"
    assert github_cluster["dimension"] == "structured_output"
    assert github_cluster["evidence_count"] >= 2
    assert github_cluster["status"] in {"candidate", "corroborated", "measured", "acknowledged"}
    assert github_cluster["attribution_state"] in {"observed_only", "temporally_associated", "provider_confirmed", "insufficient_evidence"}
    assert status_cluster["evidence_count"] == 1


def test_cluster_evidence_does_not_mark_measured_without_probe_reproduction() -> None:
    records = [
        {
            "provider": "github",
            "source_url": "https://github.com/openai/openai-python/issues/5000",
            "observed_at": "2026-10-08T09:00:00Z",
            "product": "openai/chat-completions",
            "dimension": "structured_output",
            "classification": {
                "is_change_report": True,
                "dimension": "structured_output",
                "direction": "changed",
                "first_hand": True,
                "contains_reproducible_example": True,
                "measurement_reproduced": False,
            },
        },
        {
            "provider": "status_page",
            "source_url": "https://status.openai.com/incidents/xyz",
            "observed_at": "2026-10-08T10:00:00Z",
            "product": "openai/chat-completions",
            "dimension": "structured_output",
            "classification": {
                "is_change_report": True,
                "dimension": "structured_output",
                "direction": "changed",
                "first_hand": False,
                "contains_reproducible_example": False,
                "provider_acknowledged": True,
            },
        },
    ]

    clusters = cluster_evidence(records)
    github_cluster = next(cluster for cluster in clusters if cluster["provider"] == "github")
    status_cluster = next(cluster for cluster in clusters if cluster["provider"] == "status_page")

    assert github_cluster["status"] in {"candidate", "corroborated"}
    assert status_cluster["status"] in {"candidate", "corroborated"}


def test_single_family_signal_without_measurement_stays_candidate() -> None:
    records = [
        {
            "provider": "github",
            "source_url": "https://github.com/openai/openai-python/pull/2733",
            "observed_at": "2026-10-08T09:00:00Z",
            "product": "openai",
            "dimension": "structured_output",
            "classification": {
                "is_change_report": True,
                "dimension": "structured_output",
                "direction": "changed",
                "first_hand": False,
                "contains_reproducible_example": True,
                "measurement_reproduced": False,
            },
        },
        {
            "provider": "github",
            "source_url": "https://github.com/openai/openai-python/issues/4040",
            "observed_at": "2026-10-08T09:30:00Z",
            "product": "openai",
            "dimension": "structured_output",
            "classification": {
                "is_change_report": True,
                "dimension": "structured_output",
                "direction": "changed",
                "first_hand": False,
                "contains_reproducible_example": True,
                "measurement_reproduced": False,
            },
        },
    ]

    clusters = cluster_evidence(records)
    assert len(clusters) == 1
    assert clusters[0]["status"] == "candidate"
    assert clusters[0]["attribution_state"] in {"observed_only", "temporally_associated"}


def test_attribution_provider_confirmed_requires_more_than_provider_signal() -> None:
    assert summarize_attribution_state(
        score=10,
        provider_confirmation="acknowledged",
        measurement="not_reproduced",
        independent_reports=1,
    ) == "temporally_associated"

    assert summarize_attribution_state(
        score=10,
        provider_confirmation="acknowledged",
        measurement="reproduced",
        independent_reports=1,
    ) == "provider_confirmed"


def test_grade_evidence_ranks_high_quality_evidence() -> None:
    grade = grade_evidence(
        volume="high",
        independence="high",
        reproducibility="shared_prompt_output_examples",
        measurement="reproduced",
        provider_confirmation="acknowledged",
        recency="ongoing",
    )

    assert grade["status"] == "acknowledged"
    assert grade["attribution_state"] == "provider_confirmed"
    assert grade["summary"]


def test_status_summary_uses_candidate_when_single_family_only() -> None:
    grade = summarize_status(
        evidence_count=1,
        families=1,
        measurement_observed=False,
        provider_confirmed=False,
    )
    assert grade == "candidate"


def test_cluster_evidence_counts_only_distinct_authors_as_independent() -> None:
    records = [
        {
            "provider": "forum",
            "source_url": "https://example.com/thread/1",
            "observed_at": "2026-10-08T09:00:00Z",
            "product": "openai",
            "dimension": "rate_quota",
            "author_hash": "hash-a",
            "classification": {"is_change_report": True, "dimension": "rate_quota", "direction": "worse"},
        },
        {
            "provider": "forum",
            "source_url": "https://example.com/thread/1",
            "observed_at": "2026-10-08T09:05:00Z",
            "product": "openai",
            "dimension": "rate_quota",
            "author_hash": "hash-a",
            "classification": {"is_change_report": True, "dimension": "rate_quota", "direction": "worse"},
        },
        {
            "provider": "forum",
            "source_url": "https://example.com/thread/2",
            "observed_at": "2026-10-08T09:10:00Z",
            "product": "openai",
            "dimension": "rate_quota",
            "author_hash": "hash-b",
            "classification": {"is_change_report": True, "dimension": "rate_quota", "direction": "worse"},
        },
    ]

    cluster = cluster_evidence(records)[0]
    assert cluster["independent_reports"] == 2
    assert cluster["evidence_count"] == 2


def test_condition_set_supports_versioned_rules() -> None:
    rules = ConditionSet(version="2026.10")
    assert rules.version == "2026.10"
    assert rules.rules["status_priority"]["candidate"] == 0
