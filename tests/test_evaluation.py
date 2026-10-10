from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.services.evaluation import EvaluationService, replay_evidence_window


def test_replay_evidence_window_filters_by_cutoff() -> None:
    evidence = [
        {"id": "e-1", "observed_at": datetime(2026, 9, 10, tzinfo=timezone.utc), "product": "openai/chat-completions"},
        {"id": "e-2", "observed_at": datetime(2026, 9, 12, tzinfo=timezone.utc), "product": "openai/chat-completions"},
        {"id": "e-3", "observed_at": datetime(2026, 9, 15, tzinfo=timezone.utc), "product": "anthropic/claude"},
    ]

    replayed = replay_evidence_window(evidence, cutoff=datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc))

    assert [item["id"] for item in replayed] == ["e-1", "e-2"]


def test_evaluation_service_measures_recall_and_false_positive_rate() -> None:
    episodes = [
        {
            "episode_id": "ep-1",
            "product": "openai/chat-completions",
            "dimension": "structured_output",
            "type": "acknowledged",
            "onset": "2026-09-11T00:00:00Z",
            "acknowledgment_time": "2026-09-14T00:00:00Z",
        },
        {
            "episode_id": "ep-2",
            "product": "anthropic/claude",
            "dimension": "tool_calling",
            "type": "silent_confirmed",
            "onset": "2026-09-12T00:00:00Z",
            "acknowledgment_time": "2026-09-15T00:00:00Z",
        },
        {
            "episode_id": "ep-3",
            "product": "google/gemini",
            "dimension": "rate_quota",
            "type": "control",
            "onset": "2026-09-13T00:00:00Z",
            "acknowledgment_time": None,
        },
    ]
    evidence = [
        {"id": "ev-1", "product": "openai/chat-completions", "dimension": "structured_output", "observed_at": "2026-09-12T00:00:00Z"},
        {"id": "ev-2", "product": "anthropic/claude", "dimension": "tool_calling", "observed_at": "2026-09-13T00:00:00Z"},
    ]

    report = EvaluationService().evaluate(episodes=episodes, evidence=evidence)

    assert report["episodes_total"] == 3
    assert report["confirmed_episodes"] == 2
    assert report["recall"] == 1.0
    assert report["false_positive_rate"] == 0.0
    assert report["baseline"] == "status_page_plus_manual_search"
    assert report["mean_detection_lead_time_days"] >= 0.0


def test_evaluation_api_route_returns_report() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/evaluation/run",
        json={
            "episodes": [
                {
                    "episode_id": "ep-1",
                    "product": "openai/chat-completions",
                    "dimension": "structured_output",
                    "type": "acknowledged",
                    "onset": "2026-09-11T00:00:00Z",
                    "acknowledgment_time": "2026-09-14T00:00:00Z",
                },
                {
                    "episode_id": "ep-2",
                    "product": "anthropic/claude",
                    "dimension": "tool_calling",
                    "type": "silent_confirmed",
                    "onset": "2026-09-12T00:00:00Z",
                    "acknowledgment_time": "2026-09-15T00:00:00Z",
                },
                {
                    "episode_id": "ep-3",
                    "product": "google/gemini",
                    "dimension": "rate_quota",
                    "type": "control",
                    "onset": "2026-09-13T00:00:00Z",
                    "acknowledgment_time": None,
                },
            ],
            "evidence": [
                {"product": "openai/chat-completions", "dimension": "structured_output", "observed_at": "2026-09-12T00:00:00Z"},
                {"product": "anthropic/claude", "dimension": "tool_calling", "observed_at": "2026-09-13T00:00:00Z"},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["baseline"] == "status_page_plus_manual_search"
    assert payload["episodes_total"] == 3
    assert payload["recall"] == 1.0
