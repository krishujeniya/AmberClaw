"""Shared helpers for the data-science agents.

Exports are resolved lazily so importing the package does not pull plotting
backends (matplotlib/plotly) into code paths that only need text helpers.
"""

from importlib import import_module
from typing import Any

_LAZY_EXPORTS: dict[str, str] = {
    # HTML
    "open_html_file_in_browser": "amberclaw.data.utils.html",
    # Dataset loading
    "load_data": "amberclaw.data.utils.loader",
    # Run logging
    "log_ai_function": "amberclaw.data.utils.logging",
    "log_ai_error": "amberclaw.data.utils.logging",
    # Message helpers
    "get_tool_call_names": "amberclaw.data.utils.messages",
    "get_last_user_message_content": "amberclaw.data.utils.messages",
    # Reproducible pipeline snapshots
    "strip_markdown_code_fences": "amberclaw.data.utils.pipeline",
    "pick_latest_dataset_id": "amberclaw.data.utils.pipeline",
    "pick_latest_dataset_id_any_stage": "amberclaw.data.utils.pipeline",
    "build_dataset_lineage_ids": "amberclaw.data.utils.pipeline",
    "build_dataset_dag_ids": "amberclaw.data.utils.pipeline",
    "compute_pipeline_hash": "amberclaw.data.utils.pipeline",
    "build_reproducible_pipeline_script": "amberclaw.data.utils.pipeline",
    "build_pipeline_snapshot": "amberclaw.data.utils.pipeline",
    # Plot rendering
    "matplotlib_from_base64": "amberclaw.data.utils.matplotlib",
    "plotly_from_dict": "amberclaw.data.utils.plotly",
    # Text / code formatting
    "relocate_imports_inside_function": "amberclaw.data.utils.regex",
    "add_comments_to_top": "amberclaw.data.utils.regex",
    "format_agent_name": "amberclaw.data.utils.regex",
    "format_recommended_steps": "amberclaw.data.utils.regex",
    "get_generic_summary": "amberclaw.data.utils.regex",
    "remove_consecutive_duplicates": "amberclaw.data.utils.regex",
    # Code execution
    "run_code_sandboxed_subprocess": "amberclaw.data.utils.sandbox",
}

__all__ = [
    "add_comments_to_top",
    "build_dataset_dag_ids",
    "build_dataset_lineage_ids",
    "build_pipeline_snapshot",
    "build_reproducible_pipeline_script",
    "compute_pipeline_hash",
    "format_agent_name",
    "format_recommended_steps",
    "get_generic_summary",
    "get_last_user_message_content",
    "get_tool_call_names",
    "load_data",
    "log_ai_error",
    "log_ai_function",
    "matplotlib_from_base64",
    "open_html_file_in_browser",
    "pick_latest_dataset_id",
    "pick_latest_dataset_id_any_stage",
    "plotly_from_dict",
    "relocate_imports_inside_function",
    "remove_consecutive_duplicates",
    "run_code_sandboxed_subprocess",
    "strip_markdown_code_fences",
]


def __getattr__(name: str) -> Any:
    """Resolve a public helper on first access and cache it on the package."""
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
