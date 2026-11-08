"""Characterize ordering and passthrough behavior of schema validation."""

from typing import Any

from amberclaw.agent.tools.base import Tool


class _ContractTool(Tool):
    def __init__(self, schema: dict[str, Any]) -> None:
        self.schema = schema

    @property
    def name(self) -> str:
        return "contract"

    @property
    def description(self) -> str:
        return "Offline validation contract"

    @property
    def parameters(self) -> dict[str, Any]:
        return self.schema

    async def execute(self, **_kwargs: Any) -> str:
        return "ok"


def test_nested_validation_error_order() -> None:
    tool = _ContractTool(
        {
            "type": "object",
            "required": ["token", "mode"],
            "properties": {
                "count": {"type": "integer", "enum": [2], "minimum": 1},
                "name": {"type": "string", "maxLength": 4},
                "entries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id"],
                        "properties": {"id": {"type": "string"}},
                    },
                },
            },
        }
    )
    assert tool.validate_params(
        {"count": 0, "name": "abcdef", "entries": [{}, {"id": False}]}
    ) == [
        "missing required token",
        "missing required mode",
        "count must be one of [2]",
        "count must be >= 1",
        "name must be at most 4 chars",
        "missing required entries[0].id",
        "entries[1].id should be string",
    ]


def test_string_subclass_and_unknown_values_pass_through() -> None:
    class Text(str):
        pass

    value = Text("kept")
    unknown = object()
    tool = _ContractTool({"type": "object", "properties": {"text": {"type": "string"}}})
    result = tool.cast_params({"text": value, "unknown": unknown})
    assert result["text"] is value
    assert result["unknown"] is unknown
    assert tool._cast_object(unknown, tool.parameters) is unknown
