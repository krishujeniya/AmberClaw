import json
from pathlib import Path
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from amberclaw.api.main import app
from amberclaw.api.openapi import export_openapi_schema


@pytest.fixture
def client():
    return TestClient(app)


def test_unauthenticated_api_error_envelope(client):
    response = client.get("/api/v1/agents")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] in ["UNAUTHORIZED", "HTTP_ERROR"]
    assert "message" in error
    assert "request_id" in error


def test_404_api_error_envelope(client):
    response = client.get("/api/v1/non_existent_route_12345")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "NOT_FOUND"
    assert "request_id" in error


def test_openapi_contract_export(tmp_path: Path):
    out_file = tmp_path / "openapi.json"
    exported = export_openapi_schema(app, output_path=out_file)
    assert exported.exists()

    content = json.loads(exported.read_text(encoding="utf-8"))
    assert content["openapi"].startswith("3.")
    assert "components" in content
    assert "securitySchemes" in content["components"]
    assert "BearerAuth" in content["components"]["securitySchemes"]
    assert "ApiKeyAuth" in content["components"]["securitySchemes"]
