from typing import Any
from pydantic import BaseModel, Field

from loguru import logger

from amberclaw.agent.tools.base import PydanticTool


class EDAArgs(BaseModel):
    """Arguments for the data_eda tool."""

    file_path: str = Field(..., description="Path to CSV or Excel file to analyze.")
    instructions: str = Field(
        "Perform a comprehensive EDA.", description="Optional EDA instructions."
    )


class DataEDATool(PydanticTool):
    """Run exploratory data analysis using the DataAgent EDAToolsAgent."""

    def __init__(self, model: Any = None):
        self._model = model

    @property
    def name(self) -> str:
        return "data_eda"

    @property
    def description(self) -> str:
        return (
            "Run exploratory data analysis on a dataset. "
            "Generates summary statistics, correlation analysis, "
            "missing value reports, and distribution insights."
        )

    @property
    def args_schema(self) -> type[EDAArgs]:
        return EDAArgs


    async def run(self, args: EDAArgs) -> str:
        try:
            import pandas as pd
            from amberclaw.data.ds_agents.eda_tools_agent import EDAToolsAgent

            file_path = args.file_path
            df = (
                pd.read_csv(file_path)
                if not file_path.endswith((".xlsx", ".xls"))
                else pd.read_excel(file_path)
            )

            agent = EDAToolsAgent(model=self._model)
            agent.invoke_agent(user_instructions=args.instructions, data_raw=df)


            ai_msg = agent.get_ai_message()
            if ai_msg:
                return str(ai_msg)
            return "EDA completed but no summary was generated."
        except Exception as e:
            logger.error("DataEDATool error: {}", e)
            return f"Error: {e}"
