from app.services.extraction import classify_report, resolve_dimension, resolve_product
from app.services.issue_import import IssueImportPipeline


def test_structured_output_classification_for_github_issue() -> None:
    report = {
        "title": "Structured output broke in OpenAI Chat Completions",
        "body": "After the latest deploy, JSON schema responses started failing validation and returned malformed fields.",
        "url": "https://github.com/openai/openai-cookbook/issues/42",
        "source": "github",
    }

    classification = classify_report(report)

    assert classification["is_change_report"] is True
    assert classification["dimension"] == "structured_output"
    assert classification["direction"] == "worse"
    assert resolve_dimension(report["title"] + " " + report["body"]) == "structured_output"
    assert resolve_product(report["title"] + " " + report["body"]) == "openai/chat-completions"


def test_issue_import_pipeline_ingests_real_github_issue(monkeypatch) -> None:
    class DummyResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    issue_payload = {
        "title": "OpenAI Chat Completions structured output regressed after rollout",
        "body": "This started failing JSON schema validation for tool calls and chat-completions response_format outputs.",
        "html_url": "https://github.com/openai/openai-cookbook/issues/42",
        "updated_at": "2026-10-08T12:00:00Z",
        "user": {"login": "alice"},
    }

    def fake_get(url, timeout, headers):
        assert "api.github.com/repos/openai/openai-cookbook/issues/42" in url
        return DummyResponse(issue_payload)

    monkeypatch.setattr("app.services.github_adapter.httpx.get", fake_get)

    pipeline = IssueImportPipeline()
    result = pipeline.import_issue("https://github.com/openai/openai-cookbook/issues/42")

    assert result["source_type"] == "github"
    assert result["product"] == "openai/chat-completions"
    assert result["dimension"] == "structured_output"
    assert result["classification"]["is_change_report"] is True
    assert result["evidence"]["source_url"] == "https://github.com/openai/openai-cookbook/issues/42"
    assert result["evidence"]["id"]
