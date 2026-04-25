"""DataAgent Data Cleaning tool — AI-powered dataset cleaning."""

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

    @property
    def name(self) -> str:
        return "data_clean_data"

    @property
    def description(self) -> str:
        return (
            "Clean a dataset automatically using AI. "
            "Handles missing values, duplicates, outliers, and type normalization. "
            "Returns the path to the cleaned file."
        )

    @property
    def args_schema(self) -> type[CleanArgs]:
        return CleanArgs

    def __init__(self, output_dir: str | None = None):
        super().__init__()
        self._output_dir = output_dir

    async def run(self, args: CleanArgs) -> str:
        try:
            import asyncio
            from amberclaw.data.agents import DataCleaningAgent

            df = await asyncio.to_thread(_load_data, args.file_path)

            agent = DataCleaningAgent(bypass_recommended_steps=True, bypass_explain_code=True)

            # Offload the heavy AI/Data processing to a thread
            await asyncio.to_thread(
                agent.invoke_agent,
                data_raw=df,
                user_instructions=args.instructions or None,
                max_retries=2,
            )

            cleaned = agent.get_data_cleaned()
            if cleaned is not None:
                out_path = args.file_path.rsplit(".", 1)[0] + "_cleaned.csv"
                await asyncio.to_thread(cleaned.to_csv, out_path, index=False)

                summary = agent.response.get("data_cleaning_summary", "Cleaning complete.")
                return f"{summary}\n\nCleaned data saved to: {out_path}\nRows: {len(df)} → {len(cleaned)}"

            error = agent.response.get("data_cleaner_error", "Unknown error")
            return f"Cleaning failed: {error}"
        except Exception as e:
            logger.error("DataCleanTool error: {}", e)
            return f"Error: {e}"
