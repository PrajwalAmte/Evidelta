from app.services.replay import IssueReplayService
from app.services.synthesis import SynthesisService


def test_synthesis_service_generates_honest_summary_with_citations() -> None:
    cluster = {
        "cluster_id": "github:openai/chat-completions:structured_output:2026-10-08",
        "provider": "github",
        "product": "openai/chat-completions",
        "dimension": "structured_output",
        "time_window": "2026-10-08",
        "evidence_count": 3,
        "independent_reports": 2,
        "duplicates": 0,
        "first_hand_reports": 2,
        "hearsay_reports": 1,
        "reproduced_reports": 2,
        "not_reproduced_reports": 1,
        "provider_acknowledged": False,
        "recency": "recent",
        "status": "candidate",
        "grade": "medium",
        "attribution_state": "temporally_associated",
        "records": [
            {
                "source_url": "https://github.com/openai/openai-python/pull/2733",
                "provider": "github",
                "product": "openai/chat-completions",
                "dimension": "structured_output",
            },
            {
                "source_url": "https://github.com/openai/openai-python/issues/4023",
                "provider": "github",
                "product": "openai/chat-completions",
                "dimension": "structured_output",
            },
            {
                "source_url": "https://status.openai.com/incidents/abc",
                "provider": "status_page",
                "product": "openai/chat-completions",
                "dimension": "structured_output",
            },
        ],
    }

    output = SynthesisService().synthesize_cluster(cluster)

    assert output["summary"]
    assert output["citations"]
    assert output["attribution_state"] in {"observed_only", "temporally_associated", "provider_confirmed", "insufficient_evidence"}
    assert output["confidence"] in {"low", "medium", "high"}
    assert output["evidence_quality"] in {"low", "medium", "high"}
    assert "measured" not in output["summary"].lower()
    assert "acknowledged" not in output["summary"].lower()


def test_replay_validation_reports_honest_outcomes(monkeypatch) -> None:
    def make_response(title: str, body: str, updated_at: str = "2026-10-08T12:00:00Z") -> object:
        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"title": title, "body": body, "html_url": "", "updated_at": updated_at, "user": {"login": "tester"}}

        return DummyResponse()

    call_count = 0

    def fake_get(url: str, timeout: float, headers: dict) -> object:
        nonlocal call_count
        call_count += 1
        if "openai-python/issues/4023" in url:
            return make_response("Minor dependency bump", "Updated dependency version.")
        if "openai-python/issues/2733" in url:
            return make_response(
                "OpenAI Chat Completions structured output regression",
                "JSON schema validation is failing for chat-completions structured output responses after rollout.",
            )
        return make_response("", "")

    monkeypatch.setattr("app.services.github_adapter.httpx.get", fake_get)

    service = IssueReplayService()
    result = service.replay_issue("https://github.com/openai/openai-python/pull/2733")

    assert result["status"] == "evidence_ready"

    evaluation = SynthesisService().evaluate_historical_replay(
        cases=[
            {
                "name": "structured-output regression",
                "issue_url": "https://github.com/openai/openai-python/pull/2733",
                "manual_baseline": "structured_output regression with clear evidence",
                "expected_dimension": "structured_output",
                "expected_product": "openai/chat-completions",
            },
            {
                "name": "weak issue",
                "issue_url": "https://github.com/openai/openai-python/issues/4023",
                "manual_baseline": "not enough evidence for a claim",
                "expected_dimension": "unknown",
                "expected_product": "openai",
            },
        ],
    )

    assert evaluation["total_cases"] == 2
    assert evaluation["helpful_cases"] >= 1
    assert evaluation["missed_cases"] >= 0
    assert evaluation["overstated_cases"] >= 0
    assert evaluation["insufficient_evidence_handled"] >= 1
