"""Agent-to-Agent (A2A) JSON-RPC 2.0 collaboration endpoints."""

from typing import Any

from fastapi import APIRouter, Request
from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.agent.learning.a2a import execute_local_task

router = APIRouter()


class JsonRpcRequest(BaseModel):
    jsonrpc: str = Field("2.0", pattern="^2.0$")
    method: str
    params: dict[str, Any] | list[Any] | None = None
    id: int | str | None = None


class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Any = None
    error: dict[str, Any] | None = None
    id: int | str | None = None


@router.post("")
async def handle_a2a_request(request: Request) -> JsonRpcResponse:
    """JSON-RPC 2.0 endpoint for Agent-to-Agent delegation."""
    try:
        body = await request.json()
    except Exception:
        return JsonRpcResponse(
            error={"code": -32700, "message": "Parse error"},
            id=None,
        )

    # Validate JSON-RPC 2.0 Request Object
    try:
        rpc_req = JsonRpcRequest(**body)
    except Exception as e:
        return JsonRpcResponse(
            error={"code": -32600, "message": f"Invalid Request: {e}"},
            id=body.get("id") if isinstance(body, dict) else None,
        )

    method = rpc_req.method
    params = rpc_req.params or {}
    rpc_id = rpc_req.id

    result = None
    error = None

    if method == "execute_task":
        if not isinstance(params, dict) or "task" not in params:
            error = {"code": -32602, "message": "Invalid params: 'task' parameter is required"}
        else:
            task = params["task"]
            try:
                logger.info("A2A: Received execute_task request for task '{}'", task)
                output = await execute_local_task(task)
                result = {"output": output, "status": "success"}
            except Exception as e:
                logger.exception("A2A: Internal error executing local task")
                error = {"code": -32603, "message": f"Internal error: {e}"}

    elif method == "get_capabilities":
        result = {"capabilities": ["execute_task", "get_capabilities"]}

    else:
        error = {"code": -32601, "message": f"Method not found: {method}"}

    return JsonRpcResponse(result=result, error=error, id=rpc_id)
