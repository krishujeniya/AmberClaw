"""VibeDS Exploratory Data Analysis tool."""

from typing import Any

from loguru import logger

from amberclaw.agent.tools.base import Tool


class VibeEDATool(Tool):
    """Run exploratory data analysis using the VibeDS EDAToolsAgent."""

    name = "vibeds_eda"
    description = (
        "Run exploratory data analysis on a dataset. "
        "Generates summary statistics, correlation analysis, "
        "missing value reports, and distribution insights."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to CSV or Excel file to analyze.",
            },
            "instructions": {
                "type": "string",
                "description": "EDA instructions (e.g. 'focus on correlations with target column').",
            },
        },
        "required": ["file_path"],
    }

    async def execute(self, file_path: str, instructions: str = "Perform a comprehensive EDA.", **kwargs: Any) -> str:
        try:
            import pandas as pd
            from amberclaw.vibeds.ds_agents import EDAToolsAgent

            df = pd.read_csv(file_path) if not file_path.endswith((".xlsx", ".xls")) else pd.read_excel(file_path)

            agent = EDAToolsAgent()
            agent.invoke_agent(user_instructions=instructions, data_raw=df)

            ai_msg = agent.get_ai_message()
            if ai_msg:
                return str(ai_msg)
            return "EDA completed but no summary was generated."
        except Exception as e:
            logger.error("VibeEDATool error: {}", e)
            return f"Error: {e}"
