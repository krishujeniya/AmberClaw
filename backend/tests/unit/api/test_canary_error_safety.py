"""Canary secret leakage and stream failure tests (CL-009 / A10)."""

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

from amberclaw.api.deps import get_chat_service
from amberclaw.api.errors import http_exception_handler
from amberclaw.api.v1.chat import router as chat_router
from amberclaw.services.chat_service import ChatService

CANARY_API_KEY = "canary_provider_key_xyz9876543210"
CANARY_BEARER_TOKEN = "Bearer canary_auth_token_9918273645"
CANARY_PRIVATE_PATH = "/home/ai/Documents/projects/private/keys.json"


class ExplodingProviderRuntime:
    """Runtime that raises an exception embedding multiple canary secrets."""

    async def process_direct(self, *args, **kwargs) -> str:
        raise RuntimeError(
            f"Provider failed with auth {CANARY_BEARER_TOKEN}, key={CANARY_API_KEY}, path={CANARY_PRIVATE_PATH}"
        )


@pytest.fixture
def exploding_app():
    app = FastAPI()
    app.add_exception_handler(HTTPException, http_exception_handler)
    runtime = ExplodingProviderRuntime()
    service = ChatService(runtime=runtime)

    app.include_router(chat_router, prefix="/api/v1/chat")
    app.dependency_overrides[get_chat_service] = lambda: service
    return app


def test_http_error_does_not_leak_canaries(exploding_app):
    client = TestClient(exploding_app, raise_server_exceptions=False)

    res = client.post("/api/v1/chat", json={"message": "Trigger failure"})

    assert res.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    data = res.json()
    response_text = str(data)

    assert CANARY_API_KEY not in response_text
    assert CANARY_BEARER_TOKEN not in response_text
    assert CANARY_PRIVATE_PATH not in response_text
    assert data["error"]["code"] == "HTTP_ERROR"
    assert "internal server error" in data["error"]["message"].lower()
    assert "request_id" in data["error"]


def test_sse_stream_error_does_not_leak_canaries(exploding_app):
    client = TestClient(exploding_app, raise_server_exceptions=False)

    res = client.post("/api/v1/chat/stream", json={"message": "Trigger stream failure"})

    assert res.status_code == status.HTTP_200_OK
    assert "text/event-stream" in res.headers["content-type"]
    stream_content = res.text

    assert CANARY_API_KEY not in stream_content
    assert CANARY_BEARER_TOKEN not in stream_content
    assert CANARY_PRIVATE_PATH not in stream_content
    assert "STREAM_ERROR" in stream_content
    assert "internal error" in stream_content.lower()


def test_client_4xx_sanitizes_credentials():
    app = FastAPI()
    app.add_exception_handler(HTTPException, http_exception_handler)

    @app.get("/test-400")
    def trigger_400():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid authorization {CANARY_BEARER_TOKEN} accessing {CANARY_PRIVATE_PATH}",
        )

    client = TestClient(app)
    res = client.get("/test-400")

    assert res.status_code == status.HTTP_400_BAD_REQUEST
    data = res.json()
    message = data["error"]["message"]

    assert CANARY_API_KEY not in message
    assert "canary_auth_token" not in message
    assert "/home/ai" not in message
    assert "Bearer [REDACTED]" in message
    assert "[REDACTED_PATH]" in message
