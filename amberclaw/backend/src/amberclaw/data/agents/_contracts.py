"""Typed boundaries shared by the vendored data agents.

Graph factories and tool artifacts have runtime-selected schemas. Individual nodes
retain their concrete TypedDict state; the public graph handle is schema-agnostic.
"""
import json

from collections.abc import Callable, Sequence
from typing import Any, TypeAlias, cast

from IPython.display import Markdown, Image, display
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import BaseMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer as Checkpointer

AgentGraph: TypeAlias = CompiledStateGraph[Any, Any, Any, Any]
LanguageModel: TypeAlias = BaseLanguageModel[Any]
# JSON parsed from LLMs, arbitrary tool artifacts, and provider keyword arguments.
JsonDict: TypeAlias = dict[str, Any]


def as_markdown(text: str | None) -> Markdown:
    """Bridge IPython's unannotated display constructor at one library boundary."""
    constructor = cast(Callable[[str | None], Markdown], Markdown)
    return constructor(text)


def text_value(value: object) -> str | None:
    """Read a nullable text field from a graph response without assuming its shape."""
    return value if isinstance(value, str) else None


def message_list(value: object) -> list[BaseMessage]:
    """Read concrete messages from an optional graph response field."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [message for message in value if isinstance(message, BaseMessage)]


def display_png(png: bytes) -> None:
    """Render a graph through IPython's unannotated display API."""
    image_constructor = cast(Callable[[bytes], Image], Image)
    display_image = cast(Callable[[Image], None], display)
    display_image(image_constructor(png))


def json_object(text: str) -> JsonDict | None:
    """Decode a report only when its JSON value is an object."""
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def summary_report(value: object) -> JsonDict | None:
    """Read the last concrete message report, allowing absent or malformed output."""
    messages = message_list(value)
    if not messages:
        return None
    return json_object(messages[-1].text())
