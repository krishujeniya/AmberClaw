"""Base class for agent tools."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from typing import Any, ClassVar, TypeVar, overload

from langchain_core.tools import BaseTool
from pydantic import BaseModel


class Tool(ABC):
    """
    Abstract base class for agent tools.

    Tools are capabilities that the agent can use to interact with
    the environment, such as reading files, executing commands, etc.
    """

    _TYPE_MAP: ClassVar[dict[str, type[Any] | tuple[type[Any], ...]]] = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name used in function calls."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the tool does."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for tool parameters."""
        pass

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """
        Execute the tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters.

        Returns:
            String result of the tool execution.
        """
        pass

    def cast_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Apply safe schema-driven casts before validation."""
        schema = self.parameters or {}
        if schema.get("type", "object") != "object":
            return params

        result: object = self._cast_object(params, schema)
        if not isinstance(result, dict):
            raise TypeError("Object schema casting must return a parameter dictionary")
        return result

    @overload
    def _cast_object(
        self, obj: dict[str, Any], schema: dict[str, Any]
    ) -> dict[str, Any]: ...

    @overload
    def _cast_object(self, obj: object, schema: dict[str, Any]) -> object: ...

    def _cast_object(self, obj: object, schema: dict[str, Any]) -> object:
        """Cast an object (dict) according to schema."""
        if not isinstance(obj, dict):
            return obj

        props = schema.get("properties", {})
        result: dict[str, Any] = {}

        for key, value in obj.items():
            if key in props:
                result[key] = self._cast_value(value, props[key])
            else:
                result[key] = value

        return result

    def _cast_value(self, val: Any, schema: dict[str, Any]) -> Any:
        """Cast a single value according to schema."""
        target_type = schema.get("type")
        if target_type == "array" and isinstance(val, list):
            item_schema = schema.get("items")
            return (
                [self._cast_value(item, item_schema) for item in val]
                if item_schema
                else val
            )

        if target_type == "object" and isinstance(val, dict):
            return self._cast_object(val, schema)

        return self._cast_scalar(val, target_type)

    def _cast_scalar(self, val: Any, target_type: Any) -> Any:
        """Apply scalar casts while retaining values that cannot be coerced."""
        if target_type not in self._TYPE_MAP:
            return val
        if target_type == "integer":
            return self._cast_numeric_string(val, int)
        if target_type == "number":
            return self._cast_numeric_string(val, float)
        if target_type == "string":
            return val if val is None or isinstance(val, str) else str(val)
        if target_type == "boolean":
            return self._cast_boolean(val)
        return val

    @staticmethod
    def _cast_numeric_string(val: Any, converter: Callable[[str], int | float]) -> Any:
        if isinstance(val, str):
            try:
                return converter(val)
            except ValueError:
                return val
        return val

    @staticmethod
    def _cast_boolean(val: Any) -> Any:
        if not isinstance(val, str):
            return val
        val_lower = val.lower()
        if val_lower in ("true", "1", "yes"):
            return True
        if val_lower in ("false", "0", "no"):
            return False
        return val

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate tool parameters against JSON schema. Returns error list (empty if valid)."""
        if not isinstance(params, dict):
            return [f"parameters must be an object, got {type(params).__name__}"]
        schema = self.parameters or {}
        if schema.get("type", "object") != "object":
            raise ValueError(f"Schema must be object type, got {schema.get('type')!r}")
        return self._validate(params, {**schema, "type": "object"}, "")

    def _validate(self, val: Any, schema: dict[str, Any], path: str) -> list[str]:
        t, label = schema.get("type"), path or "parameter"
        type_error = self._validate_type(val, t, label)
        if type_error is not None:
            return [type_error]

        errors = []
        if "enum" in schema and val not in schema["enum"]:
            errors.append(f"{label} must be one of {schema['enum']}")
        if t in ("integer", "number"):
            errors.extend(self._validate_numeric_bounds(val, schema, label))
        if t == "string" and isinstance(val, str):
            errors.extend(self._validate_string_bounds(val, schema, label))
        if t == "object" and isinstance(val, Mapping):
            errors.extend(self._validate_object(val, schema, path))
        if t == "array" and "items" in schema and isinstance(val, Iterable):
            errors.extend(self._validate_array(val, schema["items"], path))
        return errors

    def _validate_type(self, val: Any, t: Any, label: str) -> str | None:
        """Return the first type error before validating value constraints."""
        if t == "integer" and (not isinstance(val, int) or isinstance(val, bool)):
            return f"{label} should be integer"
        if t == "number" and (
            not isinstance(val, (int, float)) or isinstance(val, bool)
        ):
            return f"{label} should be number"
        if (
            t in self._TYPE_MAP
            and t not in ("integer", "number")
            and not isinstance(val, self._TYPE_MAP[t])
        ):
            return f"{label} should be {t}"
        return None

    @staticmethod
    def _validate_numeric_bounds(
        val: int | float, schema: dict[str, Any], label: str
    ) -> list[str]:
        """Validate minimum before maximum to preserve diagnostic ordering."""
        errors = []
        if "minimum" in schema and val < schema["minimum"]:
            errors.append(f"{label} must be >= {schema['minimum']}")
        if "maximum" in schema and val > schema["maximum"]:
            errors.append(f"{label} must be <= {schema['maximum']}")
        return errors

    @staticmethod
    def _validate_string_bounds(
        val: str, schema: dict[str, Any], label: str
    ) -> list[str]:
        """Validate string lengths using the existing error text."""
        errors = []
        if "minLength" in schema and len(val) < schema["minLength"]:
            errors.append(f"{label} must be at least {schema['minLength']} chars")
        if "maxLength" in schema and len(val) > schema["maxLength"]:
            errors.append(f"{label} must be at most {schema['maxLength']} chars")
        return errors

    def _validate_object(
        self, val: Mapping[str, Any], schema: dict[str, Any], path: str
    ) -> list[str]:
        """Report missing fields before visiting present fields in input order."""
        errors = []
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in val:
                errors.append(f"missing required {path + '.' + key if path else key}")
        for key, value in val.items():
            if key in props:
                errors.extend(
                    self._validate(value, props[key], path + "." + key if path else key)
                )
        return errors

    def _validate_array(
        self, val: Iterable[Any], item_schema: dict[str, Any], path: str
    ) -> list[str]:
        """Visit array items in order, retaining their full diagnostic paths."""
        errors = []
        for index, item in enumerate(val):
            errors.extend(
                self._validate(
                    item, item_schema, f"{path}[{index}]" if path else f"[{index}]"
                )
            )
        return errors

    def to_langchain_tool(self) -> BaseTool:
        """Convert tool to LangChain BaseTool."""
        outer_self = self

        class WrappedTool(BaseTool):
            name: str = outer_self.name
            description: str = outer_self.description
            args_schema: type[BaseModel] | None = getattr(
                outer_self, "args_schema", None
            )

            async def _arun(self, *args: Any, **kwargs: Any) -> str:
                from amberclaw.security.auth import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
                    check_tool_permission,
                )

                if args:
                    return "Error: This tool accepts named arguments only."
                try:
                    check_tool_permission(outer_self.name)
                except Exception as e:
                    return f"Error: {e}"
                return await outer_self.execute(**kwargs)

            def _run(self, *args: Any, **kwargs: Any) -> str:
                raise NotImplementedError("AmberClaw tools are async-only")

        return WrappedTool()

    def to_schema(self) -> dict[str, Any]:
        """Get OpenAI-compatible tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_openai_tool(self) -> dict[str, Any]:
        """Alias for to_schema for consistency."""
        return self.to_schema()


T = TypeVar("T", bound=BaseModel)


class PydanticTool(Tool, ABC):
    """
    Tool subclass that uses Pydantic for parameter validation.
    """

    @property
    @abstractmethod
    def args_schema(self) -> type[BaseModel]:
        """Pydantic model for tool parameters."""
        pass

    @property
    def parameters(self) -> dict[str, Any]:
        """Generate JSON Schema from Pydantic model."""
        schema = self.args_schema.model_json_schema()
        # Remove titles as they can confuse some LLMs
        self._remove_titles(schema)
        return schema

    def _remove_titles(self, obj: Any) -> None:
        if isinstance(obj, dict):
            obj.pop("title", None)
            for v in obj.values():
                self._remove_titles(v)
        elif isinstance(obj, list):
            for i in obj:
                self._remove_titles(i)

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate params using Pydantic."""
        try:
            self.args_schema.model_validate(params)
            return []
        except Exception as e:
            return [str(e)]

    async def execute(self, **kwargs: Any) -> str:
        """Validate and then execute."""
        validated = self.args_schema.model_validate(kwargs)
        return await self.run(validated)

    @abstractmethod
    async def run(self, args: Any) -> str:
        """
        Inner execution logic with validated Pydantic model.
        """
        pass
