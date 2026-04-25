"""DataAgent Exploratory Data Analysis tool."""

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

    name = "data_eda"
    description = (
        "Run exploratory data analysis on a dataset. "
        "Generates summary statistics, correlation analysis, "
        "missing value reports, and distribution insights."
    )
    args_schema = EDAArgs

    async def run(self, args: EDAArgs) -> str:
        try:
            import pandas as pd
            from amberclaw.data.ds_agents import EDAToolsAgent

            file_path = args.file_path
            df = (
                pd.read_csv(file_path)
                if not file_path.endswith((".xlsx", ".xls"))
                else pd.read_excel(file_path)
            )

            agent = EDAToolsAgent()
            agent.invoke_agent(user_instructions=args.instructions, data_raw=df)

            ai_msg = agent.get_ai_message()
            if ai_msg:
                return str(ai_msg)
            return "EDA completed but no summary was generated."
        except Exception as e:
            logger.error("DataEDATool error: {}", e)
            return f"Error: {e}"
