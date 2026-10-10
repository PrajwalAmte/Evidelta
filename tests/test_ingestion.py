from datetime import datetime, timezone

import pytest

from app.services.ingestion import IngestionService, normalize_item


def test_normalize_item_preserves_core_fields() -> None:
    payload = {
        "source": "github",
        "title": "Tool calling regressed",
        "body": "Users report tool calls failing",
        "url": "https://example.com/issues/42",
        "language": "en",
    }

    normalized = normalize_item(payload)

    assert normalized["source"] == "github"
    assert normalized["title"] == "Tool calling regressed"
    assert normalized["url"] == "https://example.com/issues/42"
    assert normalized["language"] == "en"


def test_ingestion_service_records_provenance_and_replay_window() -> None:
    service = IngestionService("sqlite://")
    cutoff = datetime(2026, 9, 15, tzinfo=timezone.utc)

    first = service.ingest_evidence(
        source_type="github_issue",
        source_url="https://example.com/issues/1",
        observed_at=datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc),
        raw_content='{"issue": "tool calling broke"}',
        author_id="user-1",
    )
    second = service.ingest_evidence(
        source_type="status_page",
        source_url="https://example.com/status/2",
        observed_at=datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc),
        raw_content='{"status": "degraded"}',
        author_id="user-2",
    )

    assert first["content_hash"]
    assert first["snapshot_id"]
    replayed = service.replay_as_of(cutoff)
    assert len(replayed) == 1
    assert replayed[0]["source_url"] == "https://example.com/issues/1"
    assert second["source_url"] == "https://example.com/status/2"


def test_ingestion_rejects_naive_or_invalid_observed_timestamps() -> None:
    service = IngestionService("sqlite://")

    with pytest.raises(ValueError, match="timezone-aware"):
        service.ingest_evidence(
            source_type="github_issue",
            source_url="https://example.com/issues/invalid-naive",
            observed_at=datetime(2026, 9, 14, 10, 0),
            raw_content='{"issue": "missing timezone"}',
        )

    with pytest.raises(ValueError, match="Invalid observed_at"):
        service.ingest_evidence(
            source_type="github_issue",
            source_url="https://example.com/issues/invalid-string",
            observed_at="not-a-real-timestamp",
            raw_content='{"issue": "bad timestamp"}',
        )
