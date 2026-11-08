"""
AmberClaw Data Science Tools
"""

import asyncio
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.providers.base import LLMProvider
from amberclaw.tools.registry import BaseTool


class DataCleanArgs(BaseModel):
    file_path: str = Field(..., description="Path to CSV or Excel file to clean.")
    instructions: str | None = Field(
        None, description="Optional cleaning instructions."
    )


def _load_data(path: str) -> Any:
    import pandas as pd  # noqa: PLC0415 - load the optional runtime dependency only for this operation

    if path.endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    return pd.read_csv(path)


class DataCleanTool(BaseTool[[DataCleanArgs]]):
    name: str = "data_clean"
    description: str = "Clean a dataset automatically using AI. Handles missing values, duplicates, and outliers."
    args_schema: type[BaseModel] = DataCleanArgs

    def __init__(self, provider: LLMProvider | None = None) -> None:
        super().__init__()
        self._provider = provider

    async def run(self, args: DataCleanArgs) -> str:
        try:
            from amberclaw.data.agents import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
                DataCleaningAgent,
            )

            # Use default provider for the agent
            provider = self._provider
            if not provider:
                return "Error: No LLM provider configured."

            # Load data using sandbox or thread
            df = await asyncio.to_thread(_load_data, args.file_path)

            agent = DataCleaningAgent(model=provider.to_langchain_chat())

            # Run the agent (offload to thread as it's synchronous logic)
            await asyncio.to_thread(
                agent.invoke_agent,
                data_raw=df,
                user_instructions=args.instructions,
            )

            cleaned = agent.get_data_cleaned()
            if cleaned is not None:
                out_path = args.file_path.rsplit(".", 1)[0] + "_cleaned.csv"
                await asyncio.to_thread(cleaned.to_csv, out_path, index=False)
                return f"Cleaning complete. Cleaned data saved to: {out_path}"

            error = agent.response.get("data_cleaner_error", "Unknown error")
            return f"Cleaning failed: {error}"
        except Exception as e:
            logger.error(f"DataCleanTool error: {e}")
            return f"Error: {e}"
