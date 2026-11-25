"""Data-science tool surface.

Public tools are resolved lazily: importing :mod:`amberclaw.data.tools` must not
drag optional clients (MLflow server, H2O runtime, Sweetviz/D-Tale report
engines) into every data-module import.
"""

from importlib import import_module
from typing import Any

_LAZY_EXPORTS: dict[str, str] = {
    # DataFrame summaries
    "get_dataframe_summary": "amberclaw.data.tools.dataframe",
    # File / dataset loading
    "load_directory": "amberclaw.data.tools.data_loader",
    "load_file": "amberclaw.data.tools.data_loader",
    "list_directory_contents": "amberclaw.data.tools.data_loader",
    "list_directory_recursive": "amberclaw.data.tools.data_loader",
    "get_file_info": "amberclaw.data.tools.data_loader",
    "search_files_by_pattern": "amberclaw.data.tools.data_loader",
    "resolve_existing_file_path": "amberclaw.data.tools.data_loader",
    "auto_load_file": "amberclaw.data.tools.data_loader",
    "load_csv": "amberclaw.data.tools.data_loader",
    "load_excel": "amberclaw.data.tools.data_loader",
    "load_json": "amberclaw.data.tools.data_loader",
    "load_parquet": "amberclaw.data.tools.data_loader",
    "load_pickle": "amberclaw.data.tools.data_loader",
    # Exploratory data analysis
    "explain_data": "amberclaw.data.tools.eda",
    "describe_dataset": "amberclaw.data.tools.eda",
    "visualize_missing": "amberclaw.data.tools.eda",
    "generate_correlation_funnel": "amberclaw.data.tools.eda",
    "generate_sweetviz_report": "amberclaw.data.tools.eda",
    "generate_dtale_report": "amberclaw.data.tools.eda",
    # AutoML
    "train_h2o_automl": "amberclaw.data.tools.h2o",
    # Experiment tracking
    "mlflow_set_tags": "amberclaw.data.tools.mlflow",
    "mlflow_log_params": "amberclaw.data.tools.mlflow",
    "mlflow_log_metrics": "amberclaw.data.tools.mlflow",
    "mlflow_log_table": "amberclaw.data.tools.mlflow",
    "mlflow_log_dict": "amberclaw.data.tools.mlflow",
    "mlflow_log_figure": "amberclaw.data.tools.mlflow",
    "mlflow_log_artifact": "amberclaw.data.tools.mlflow",
    "mlflow_search_experiments": "amberclaw.data.tools.mlflow",
    "mlflow_search_runs": "amberclaw.data.tools.mlflow",
    "mlflow_create_experiment": "amberclaw.data.tools.mlflow",
    "mlflow_predict_from_run_id": "amberclaw.data.tools.mlflow",
    "mlflow_launch_ui": "amberclaw.data.tools.mlflow",
    "mlflow_stop_ui": "amberclaw.data.tools.mlflow",
    "mlflow_list_artifacts": "amberclaw.data.tools.mlflow",
    "mlflow_download_artifacts": "amberclaw.data.tools.mlflow",
    "mlflow_list_registered_models": "amberclaw.data.tools.mlflow",
    "mlflow_search_registered_models": "amberclaw.data.tools.mlflow",
    "mlflow_get_model_version_details": "amberclaw.data.tools.mlflow",
    "mlflow_get_run_details": "amberclaw.data.tools.mlflow",
    "mlflow_transition_model_version_stage": "amberclaw.data.tools.mlflow",
    "mlflow_tracking_info": "amberclaw.data.tools.mlflow",
    "mlflow_ui_status": "amberclaw.data.tools.mlflow",
    # Database metadata
    "get_database_metadata": "amberclaw.data.tools.sql",
}

__all__ = [
    "auto_load_file",
    "describe_dataset",
    "explain_data",
    "generate_correlation_funnel",
    "generate_dtale_report",
    "generate_sweetviz_report",
    "get_database_metadata",
    "get_dataframe_summary",
    "get_file_info",
    "list_directory_contents",
    "list_directory_recursive",
    "load_csv",
    "load_directory",
    "load_excel",
    "load_file",
    "load_json",
    "load_parquet",
    "load_pickle",
    "mlflow_create_experiment",
    "mlflow_download_artifacts",
    "mlflow_get_model_version_details",
    "mlflow_get_run_details",
    "mlflow_launch_ui",
    "mlflow_list_artifacts",
    "mlflow_list_registered_models",
    "mlflow_log_artifact",
    "mlflow_log_dict",
    "mlflow_log_figure",
    "mlflow_log_metrics",
    "mlflow_log_params",
    "mlflow_log_table",
    "mlflow_predict_from_run_id",
    "mlflow_search_experiments",
    "mlflow_search_registered_models",
    "mlflow_search_runs",
    "mlflow_set_tags",
    "mlflow_stop_ui",
    "mlflow_tracking_info",
    "mlflow_transition_model_version_stage",
    "mlflow_ui_status",
    "resolve_existing_file_path",
    "search_files_by_pattern",
    "train_h2o_automl",
    "visualize_missing",
]


def __getattr__(name: str) -> Any:
    """Resolve a public tool on first access and cache it on the package."""
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
