from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_probe_run_and_ingest_creates_evidence_record() -> None:
    response = client.post(
        "/api/v1/probes/ingest",
        json={
            "provider": "openai",
            "product": "openai/chat-completions",
            "dimension": "structured_output",
            "structured_outputs": [True, True, False],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ingested"
    assert payload["probe"]["dimension"] == "structured_output"
    assert payload["evidence"]["source_type"] == "probe"


def test_docs_import_endpoint_ingests_when_adapter_resolves_signal(monkeypatch) -> None:
    def fake_fetch_doc(self, url: str):
        return {
            "source_type": "docs",
            "source_url": url,
            "product": "openai/chat-completions",
            "dimension": "structured_output",
            "classification": {
                "is_change_report": True,
                "dimension": "structured_output",
                "direction": "changed",
                "first_hand": False,
                "contains_reproducible_example": False,
            },
            "observed_at": "2026-10-09T12:00:00Z",
            "raw_content": {
                "title": "API docs update",
                "body": "Structured output contract changed for response_format.",
            },
        }

    monkeypatch.setattr("app.services.docs_adapter.DocsAdapter.fetch_doc", fake_fetch_doc)

    response = client.post("/api/v1/sources/docs/import", json={"url": "https://platform.openai.com/docs/api-reference"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "imported"
    assert payload["source_type"] == "docs"
    assert payload["dimension"] == "structured_output"


def test_hackernews_import_endpoint_ingests_when_adapter_resolves_signal(monkeypatch) -> None:
    def fake_fetch_item(self, item_id: int):
        return {
            "source_type": "hackernews",
            "source_url": f"https://news.ycombinator.com/item?id={item_id}",
            "product": "openai/chat-completions",
            "dimension": "rate_quota",
            "classification": {
                "is_change_report": True,
                "dimension": "rate_quota",
                "direction": "worse",
                "first_hand": True,
                "contains_reproducible_example": True,
            },
            "observed_at": "2026-10-09T12:00:00Z",
            "raw_content": {
                "title": "Rate limits changed",
                "body": "Users report 429s and lower limits.",
                "item_id": item_id,
            },
        }

    monkeypatch.setattr("app.services.hackernews_adapter.HackerNewsAdapter.fetch_item", fake_fetch_item)

    response = client.post("/api/v1/sources/hackernews/import", json={"item_id": 12345})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "imported"
    assert payload["source_type"] == "hackernews"
    assert payload["dimension"] == "rate_quota"
