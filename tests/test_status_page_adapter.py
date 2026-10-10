from app.services.status_page_adapter import StatusPageAdapter


def test_status_page_adapter_normalizes_provider_incident(monkeypatch) -> None:
    class DummyResponse:
        def __init__(self, text: str):
            self._text = text

        def raise_for_status(self) -> None:
            return None

        @property
        def text(self) -> str:
            return self._text

    def fake_get(url: str, timeout: float, headers: dict[str, str]):
        assert "status.openai.com" in url
        return DummyResponse(
            "<html><head><title>OpenAI Status</title><meta name='description' content='OpenAI Chat Completions is experiencing structured output and latency issues.' /></head>"
            "<body>Structured output responses are failing validation across the platform. This is a provider incident affecting Chat Completions.</body></html>"
        )

    monkeypatch.setattr("app.services.status_page_adapter.httpx.get", fake_get)

    result = StatusPageAdapter().normalize_incident("https://status.openai.com/incidents/incident-20261009")

    assert result["source_type"] == "status_page"
    assert result["product"] == "openai/chat-completions"
    assert result["dimension"] == "structured_output"
    assert result["classification"]["is_change_report"] is True
    assert result["provider_name"] == "openai"
