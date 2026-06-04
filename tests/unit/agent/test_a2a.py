"""Unit tests for Agent-to-Agent (A2A) collaboration."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request

from amberclaw.agent.tools.a2a import A2ADelegateArgs, A2ADelegateTool
from amberclaw.api.v1.a2a import JsonRpcResponse, handle_a2a_request


@pytest.mark.asyncio
async def test_a2a_delegate_tool():
    tool = A2ADelegateTool()

    with patch("amberclaw.agent.tools.a2a.delegate_to_remote", return_value="Remote task completed successfully") as mock_delegate:
        res = await tool.run(A2ADelegateArgs(
            target_url="http://localhost:8000/api/v1/a2a",
            task="Check system resource usage",
        ))

        mock_delegate.assert_called_once_with("http://localhost:8000/api/v1/a2a", "Check system resource usage")
        assert res == "Remote task completed successfully"


@pytest.mark.asyncio
async def test_a2a_router_execute_task():
    # Mock FastAPI request body
    mock_request = AsyncMock(spec=Request)
    mock_request.json.return_value = {
        "jsonrpc": "2.0",
        "method": "execute_task",
        "params": {"task": "Verify file checksum"},
        "id": "test-id-1",
    }

    with patch("amberclaw.api.v1.a2a.execute_local_task", return_value="Checksum match") as mock_execute:
        res = await handle_a2a_request(mock_request)

        mock_execute.assert_called_once_with("Verify file checksum")
        assert isinstance(res, JsonRpcResponse)
        assert res.jsonrpc == "2.0"
        assert res.result == {"output": "Checksum match", "status": "success"}
        assert res.id == "test-id-1"
        assert res.error is None


@pytest.mark.asyncio
async def test_a2a_router_get_capabilities():
    mock_request = AsyncMock(spec=Request)
    mock_request.json.return_value = {
        "jsonrpc": "2.0",
        "method": "get_capabilities",
        "id": "test-id-2",
    }

    res = await handle_a2a_request(mock_request)
    assert isinstance(res, JsonRpcResponse)
    assert "execute_task" in res.result["capabilities"]
    assert res.id == "test-id-2"
    assert res.error is None


@pytest.mark.asyncio
async def test_a2a_router_method_not_found():
    mock_request = AsyncMock(spec=Request)
    mock_request.json.return_value = {
        "jsonrpc": "2.0",
        "method": "unknown_method",
        "id": "test-id-3",
    }

    expected_error_code = -32601
    res = await handle_a2a_request(mock_request)
    assert isinstance(res, JsonRpcResponse)
    assert res.error["code"] == expected_error_code
    assert "Method not found" in res.error["message"]
    assert res.id == "test-id-3"
