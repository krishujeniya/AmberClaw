"""DataAgent Data Cleaning tool — AI-powered dataset cleaning."""

from typing import Any, Optional
from pydantic import BaseModel, Field

import pandas as pd
from loguru import logger

from amberclaw.agent.tools.base import PydanticTool


class CleanArgs(BaseModel):
    """Arguments for the data_clean_data tool."""
    file_path: str = Field(..., description="Path to CSV or Excel file to clean.")
    instructions: str = Field("", description="Optional cleaning instructions.")


def _load_data(path: str) -> pd.DataFrame:
    """Load CSV or Excel into DataFrame."""
    if path.endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    return pd.read_csv(path)


class DataCleanTool(PydanticTool):
    """Clean datasets using the DataAgent DataCleaningAgent."""

    name = "data_clean_data"
    description = (
        "Clean a CSV/Excel dataset using AI-powered data cleaning. "
        "Handles missing values, type conversions, outlier removal, "
        "deduplication, and custom cleaning instructions. "
        "Returns a summary of changes made."
    )
    args_schema = CleanArgs

    def __init__(self, output_dir: str | None = None):
        super().__init__()
        self._output_dir = output_dir

    async def run(self, args: CleanArgs) -> str:
        try:
            from amberclaw.data.agents import DataCleaningAgent

            df = _load_data(args.file_path)

            agent = DataCleaningAgent(bypass_recommended_steps=True, bypass_explain_code=True)
            agent.invoke_agent(data_raw=df, user_instructions=args.instructions or None, max_retries=2)

            cleaned = agent.get_data_cleaned()
            if cleaned is not None:
                out_path = args.file_path.rsplit(".", 1)[0] + "_cleaned.csv"
                cleaned.to_csv(out_path, index=False)

                summary = agent.response.get("data_cleaning_summary", "Cleaning complete.")
                return f"{summary}\n\nCleaned data saved to: {out_path}\nRows: {len(df)} → {len(cleaned)}"

            error = agent.response.get("data_cleaner_error", "Unknown error")
            return f"Cleaning failed: {error}"
        except Exception as e:
            logger.error("DataCleanTool error: {}", e)
            return f"Error: {e}"
