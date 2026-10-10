from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_probe_runner_structured_output_success_rate() -> None:
    payload = {
        "provider": "provider-a",
        "product": "product-x",
        "dimension": "structured_output",
        "structured_outputs": [True, True, False, True],
    }

    response = client.post("/api/v1/probes/run", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["dimension"] == "structured_output"
    assert body["success_rate"] == 0.75
    assert body["status"] == "watch"


def test_probe_runner_rate_quota_headers() -> None:
    payload = {
        "provider": "provider-a",
        "product": "product-x",
        "dimension": "rate_quota",
        "headers": {
            "x-ratelimit-limit": "1000",
            "x-ratelimit-remaining": "850",
            "x-ratelimit-reset": "60",
        },
    }

    response = client.post("/api/v1/probes/run", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["output"]["limit"] == "1000"
    assert body["output"]["remaining"] == "850"
    assert body["vantage_point"]["region"] == "us-east-1"
    assert body["pass_count"] == 2
    assert body["failure_count"] == 0


def test_probe_runner_tool_calling_degraded() -> None:
    payload = {
        "provider": "provider-a",
        "product": "product-x",
        "dimension": "tool_calling",
        "tool_results": [True, False, True, False, True],
    }

    response = client.post("/api/v1/probes/run", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["dimension"] == "tool_calling"
    assert body["success_rate"] == 0.6
    assert body["status"] == "critical"


def test_probe_runner_refusal_behavior_stable() -> None:
    payload = {
        "provider": "provider-a",
        "product": "product-x",
        "dimension": "refusal_behavior",
        "refusal_responses": [
            "Here is the answer you requested.",
            "Sure, I can help with that.",
            "Here is the information you need.",
            "Of course, let me explain.",
            "Here you go.",
            "I can assist with that.",
            "Absolutely, here is the data.",
            "Here is the result.",
            "That is a great question.",
            "Let me break that down for you.",
        ],
    }

    response = client.post("/api/v1/probes/run", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["dimension"] == "refusal_behavior"
    assert body["status"] == "stable"
    assert body["output"]["refusal_rate"] == 0.0


def test_probe_runner_latency_degraded() -> None:
    payload = {
        "provider": "provider-a",
        "product": "product-x",
        "dimension": "latency",
        "latencies_ms": [6000.0, 7500.0, 8000.0],
    }

    response = client.post("/api/v1/probes/run", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["dimension"] == "latency"
    assert body["status"] == "degraded"
    assert body["output"]["average_ms"] > 5000


def test_probe_runner_availability_watch() -> None:
    payload = {
        "provider": "provider-a",
        "product": "product-x",
        "dimension": "availability",
        "error_rate": 0.04,
    }

    response = client.post("/api/v1/probes/run", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["dimension"] == "availability"
    assert body["status"] == "watch"


def test_grade_request_rejects_invalid_enum_value() -> None:
    payload = {
        "volume": "very_high",
        "independence": "high",
        "reproducibility": "none",
        "measurement": "reproduced",
        "provider_confirmation": "none",
        "recency": "ongoing",
    }

    response = client.post("/api/v1/change/grade", json=payload)

    assert response.status_code == 422
