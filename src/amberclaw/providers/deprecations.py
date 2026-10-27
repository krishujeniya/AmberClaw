"""Model and provider deprecation schedules, warnings, and migration suggestions."""

from __future__ import annotations

from loguru import logger
from pydantic import BaseModel

DEPRECATION_SCHEDULE: dict[str, dict[str, str | None]] = {
    "text-davinci-003": {
        "sunset_date": "2024-01-04",
        "replacement": "gpt-3.5-turbo",
        "notes": "Legacy Completions API shut down by OpenAI.",
    },
    "gpt-3.5-turbo-0613": {
        "sunset_date": "2024-06-13",
        "replacement": "gpt-4o-mini",
        "notes": "Snapshot pinned version sunset; migrate to gpt-4o-mini.",
    },
    "gpt-4-0314": {
        "sunset_date": "2024-06-13",
        "replacement": "gpt-4o",
        "notes": "Snapshot version retired.",
    },
    "gpt-4-0613": {
        "sunset_date": "2025-06-06",
        "replacement": "gpt-4o",
        "notes": "Deprecated in favor of GPT-4o.",
    },
    "claude-2.0": {
        "sunset_date": "2024-11-06",
        "replacement": "claude-3-5-sonnet-20241022",
        "notes": "Claude 2 series retired by Anthropic.",
    },
    "claude-2.1": {
        "sunset_date": "2024-11-06",
        "replacement": "claude-3-5-sonnet-20241022",
        "notes": "Claude 2.1 retired by Anthropic.",
    },
    "claude-instant-1.2": {
        "sunset_date": "2024-11-06",
        "replacement": "claude-3-5-haiku-20241022",
        "notes": "Claude Instant retired by Anthropic.",
    },
    "gemini-1.0-pro": {
        "sunset_date": "2025-02-15",
        "replacement": "gemini-1.5-flash",
        "notes": "Gemini 1.0 discontinued in favor of 1.5 series.",
    },
    "llama-2-7b-chat": {
        "sunset_date": None,
        "replacement": "llama-3.1-8b-instruct",
        "notes": "Llama 2 superseded by Llama 3.1.",
    },
    "llama-2-70b-chat": {
        "sunset_date": None,
        "replacement": "llama-3.1-70b-instruct",
        "notes": "Llama 2 superseded by Llama 3.1.",
    },
}


class DeprecationNotice(BaseModel):
    """Notice describing model deprecation status and migration path."""

    model: str
    is_deprecated: bool = True
    sunset_date: str | None = None
    replacement_model: str | None = None
    message: str = ""


def check_model_deprecation(model: str) -> DeprecationNotice | None:
    """Check if a model identifier is deprecated or sunset."""
    bare_model = model.rsplit("/", maxsplit=1)[-1].lower()

    for dep_key, info in DEPRECATION_SCHEDULE.items():
        if dep_key in bare_model:
            sunset = info.get("sunset_date")
            replacement = info.get("replacement")
            notes = info.get("notes", "")

            msg = (
                f"Model '{model}' is DEPRECATED"
                + (f" (sunset: {sunset})" if sunset else "")
                + (f". Recommended replacement: '{replacement}'" if replacement else "")
                + (f". {notes}" if notes else "")
            )

            return DeprecationNotice(
                model=model,
                is_deprecated=True,
                sunset_date=sunset,
                replacement_model=replacement,
                message=msg,
            )

    return None


def log_deprecation_warning(model: str) -> None:
    """Log a structured warning if model is deprecated."""
    notice = check_model_deprecation(model)
    if notice:
        logger.warning(notice.message)
