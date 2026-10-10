from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_change_feed_endpoint_returns_structured_entries() -> None:
    client.post(
        "/api/v1/ingest",
        json={
            "source_type": "github",
            "source_url": "https://github.com/openai/openai-python/pull/2733",
            "observed_at": "2026-10-08T09:00:00Z",
            "raw_content": "Structured output responses failing JSON schema validation after rollout.",
            "author_id": "ui-test-a",
        },
    )
    response = client.post(
        "/api/v1/changes/feed",
        json={"product": "openai/chat-completions", "limit": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["product"] == "openai/chat-completions"
    assert isinstance(payload["changes"], list)
    assert payload["status"] in {"ready", "no_data"}
    if payload["changes"]:
        first = payload["changes"][0]
        assert first["product"] == "openai/chat-completions"
        assert "evidence_ids" in first


def test_incident_query_endpoint_returns_evidence_summary() -> None:
    response = client.post(
        "/api/v1/incident/query",
        json={
            "product": "openai/chat-completions",
            "symptom": "structured output regression",
            "time_window": "30d",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["product"] == "openai/chat-completions"
    assert payload["symptom"] == "structured output regression"
    assert "summary" in payload
    assert isinstance(payload["evidence_ids"], list)
    assert payload["status"] in {"candidate", "corroborated", "measured", "acknowledged", "insufficient_evidence"}


def test_ui_page_is_exposed() -> None:
    response = client.get("/api/v1/ui")
    assert response.status_code == 200
    assert "Evidelta" in response.text


def test_historical_evidence_is_visible_with_365d_window() -> None:
    client.post(
        "/api/v1/ingest",
        json={
            "source_type": "forum",
            "source_url": "https://community.openai.com/t/structured-output-schema-validation-changed-without-notice-previously-valid-schemas-now-rejected/1384139/1",
            "observed_at": "2026-06-19T16:35:55Z",
            "raw_content": "We had a schema that worked for weeks and then stopped validating in the Responses API on June 18.",
            "author_id": "David_Brown2",
        },
    )
    response = client.post(
        "/api/v1/incident/query",
        json={
            "product": "all",
            "symptom": "structured output regression",
            "time_window": "365d",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"candidate", "corroborated", "measured", "acknowledged", "insufficient_evidence"}
    assert payload["evidence_ids"] or payload["status"] != "insufficient_evidence"


def test_ui_evidence_includes_text_and_extracted_fields() -> None:
    evidence_id = client.post(
        "/api/v1/ingest",
        json={
            "source_type": "github",
            "source_url": "https://github.com/openai/openai-python/issues/4040",
            "observed_at": "2026-10-08T10:00:00Z",
            "raw_content": "Structured output responses failing JSON schema validation after rollout.",
            "author_id": "ui-detail-check",
        },
    ).json()["id"]

    response = client.post("/api/v1/ui/evidence", json={"evidence_ids": [evidence_id]})
    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence"]
    item = payload["evidence"][0]
    assert "raw_text" in item
    assert "product" in item
    assert "dimension" in item
    assert "classification" in item
    assert "extraction" in item
    assert item["extraction"]["dimension"]["dimension"] == "structured_output"
    assert "structured_output" in item["dimension"]


def test_placeholder_status_urls_are_rejected() -> None:
    response = client.post(
        "/api/v1/status-page/import",
        json={"incident_url": "https://status.openai.com/incidents/abc123"},
    )
    assert response.status_code == 400
    assert "placeholder" in response.json()["detail"].lower()


def test_probe_source_url_does_not_duplicate_provider_segment() -> None:
    response = client.post(
        "/api/v1/probes/ingest",
        json={
            "provider": "openai",
            "product": "openai/chat-completions",
            "dimension": "structured_output",
            "structured_outputs": [True, False, True],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence"]["source_url"] == "probe://openai/chat-completions/structured_output"
