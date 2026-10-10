from app.services.replay import IssueReplayService


def test_replay_service_evaluates_signal_strength_for_a_real_issue(monkeypatch) -> None:
    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "title": "OpenAI Chat Completions structured output regression",
                "body": "JSON schema validation is failing for chat-completions structured output responses after rollout.",
                "html_url": "https://github.com/openai/openai-python/pull/2733",
                "updated_at": "2026-10-08T12:00:00Z",
                "user": {"login": "alice"},
            }

    monkeypatch.setattr("app.services.github_adapter.httpx.get", lambda url, timeout, headers: DummyResponse())

    service = IssueReplayService()
    result = service.replay_issue("https://github.com/openai/openai-python/pull/2733")

    assert result["source_type"] == "github"
    assert result["product"] == "openai/chat-completions"
    assert result["dimension"] == "structured_output"
    assert result["signal_score"] >= 0.7
    assert result["should_cluster"] is True
    assert result["status"] == "evidence_ready"
