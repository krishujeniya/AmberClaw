import pytest
from fastapi import status
from fastapi.testclient import TestClient

from amberclaw.api.main import app
from amberclaw.observability.metrics import record_token_usage


@pytest.fixture
def client():
    return TestClient(app)


def test_prometheus_metrics_endpoint(client):
    # Make a sample call to generate request metrics
    client.get("/health")

    response = client.get("/metrics")
    assert response.status_code == status.HTTP_200_OK
    text = response.text
    assert "amberclaw_http_requests_total" in text
    assert "amberclaw_http_request_duration_seconds" in text


def test_prometheus_token_usage_tracking(client):
    record_token_usage(model="gpt-4o", prompt_tokens=100, completion_tokens=50)

    response = client.get("/metrics")
    assert response.status_code == status.HTTP_200_OK
    text = response.text
    assert "amberclaw_llm_tokens_total" in text
    assert 'model="gpt-4o"' in text
