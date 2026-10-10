from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.main import app
from app.services.llm import CitationVerifier, LLMSynthesizer


def test_llm_synthesizer_posts_to_local_provider_endpoint(monkeypatch) -> None:
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "message": {"content": '{"summary": "Evidence is consistent.", "citations": ["E12"]}'},
        "done": True,
    }

    captured = {}

    def fake_post(url, json, timeout, **kwargs):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        captured["headers"] = kwargs.get("headers")
        return mock_response

    monkeypatch.setattr("app.services.llm.settings.llm_provider", "ollama")
    monkeypatch.setattr("app.services.llm.httpx.post", fake_post)

    result = LLMSynthesizer().generate(prompt="Summarize this evidence")

    assert captured["url"].endswith("/api/chat")
    assert captured["json"]["model"] == "qwen2.5-coder:14b-instruct"
    assert result["summary"] == "Evidence is consistent."
    assert result["citations"] == ["E12"]


def test_openrouter_synthesizer_uses_remote_provider(monkeypatch) -> None:
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"summary": "Remote evidence synthesized.", "citations": ["E77"]}'}}]
    }

    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return mock_response

    monkeypatch.setattr("app.services.llm.settings.llm_provider", "openrouter")
    monkeypatch.setattr("app.services.llm.settings.openrouter_api_key", "test-key")
    monkeypatch.setattr("app.services.llm.httpx.post", fake_post)

    result = LLMSynthesizer().generate(prompt="Summarize this evidence", evidence_ids=["E77"])

    assert captured["url"].endswith("/chat/completions")
    assert captured["json"]["model"] == "qwen/qwen-2.5-7b-instruct"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert result["summary"] == "Remote evidence synthesized."
    assert result["citations"] == ["E77"]


def test_llm_route_is_exposed(monkeypatch) -> None:
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"summary": "Evidence is consistent.", "citations": []}'}}]
    }
    monkeypatch.setattr("app.services.llm.settings.llm_provider", "openrouter")
    monkeypatch.setattr("app.services.llm.settings.openrouter_api_key", "test-key")
    monkeypatch.setattr("app.services.llm.httpx.post", lambda *a, **kw: mock_response)

    client = TestClient(app)
    response = client.post(
        "/api/v1/llm/synthesize",
        json={
            "prompt": "Explain the evidence",
            "system_prompt": "Return JSON with summary and citations.",
        },
    )

    assert response.status_code == 200


def test_citation_verifier_rejects_uncited_or_unknown_evidence() -> None:
    verifier = CitationVerifier()
    invalid = verifier.verify(
        summary="The provider was definitely confirmed to have changed behavior.",
        citations=["E99"],
        evidence_ids=["E12", "E31"],
        attribution_state="temporally_associated",
    )

    assert invalid is False

    valid = verifier.verify(
        summary="The observed evidence suggests a change in behavior.",
        citations=["E12", "E31"],
        evidence_ids=["E12", "E31"],
        attribution_state="temporally_associated",
    )

    assert valid is True
