"""VibeDS Data Cleaning tool — AI-powered dataset cleaning."""

from typing import Any

import pandas as pd
from loguru import logger

from amberclaw.agent.tools.base import Tool


def _load_data(path: str) -> pd.DataFrame:
    """Load CSV or Excel into DataFrame."""
    if path.endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    return pd.read_csv(path)


class VibeDataCleanTool(Tool):
    """Clean datasets using the VibeDS DataCleaningAgent."""

    name = "vibeds_clean_data"
    description = (
        "Clean a CSV/Excel dataset using AI-powered data cleaning. "
        "Handles missing values, type conversions, outlier removal, "
        "deduplication, and custom cleaning instructions. "
        "Returns a summary of changes made."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to CSV or Excel file to clean.",
            },
            "instructions": {
                "type": "string",
                "description": "Cleaning instructions (e.g. 'Drop columns with >50% missing').",
            },
        },
        "required": ["file_path"],
    }

    def __init__(self, output_dir: str | None = None):
        self._output_dir = output_dir

    async def execute(self, file_path: str, instructions: str = "", **kwargs: Any) -> str:
        try:
            from amberclaw.vibeds.agents import DataCleaningAgent

            df = _load_data(file_path)

            agent = DataCleaningAgent(bypass_recommended_steps=True, bypass_explain_code=True)
            agent.invoke_agent(data_raw=df, user_instructions=instructions or None, max_retries=2)

            cleaned = agent.get_data_cleaned()
            if cleaned is not None:
                out_path = file_path.rsplit(".", 1)[0] + "_cleaned.csv"
                cleaned.to_csv(out_path, index=False)

                summary = agent.response.get("data_cleaning_summary", "Cleaning complete.")
                return f"{summary}\n\nCleaned data saved to: {out_path}\nRows: {len(df)} → {len(cleaned)}"

            error = agent.response.get("data_cleaner_error", "Unknown error")
            return f"Cleaning failed: {error}"
        except Exception as e:
            logger.error("VibeDataCleanTool error: {}", e)
            return f"Error: {e}"
