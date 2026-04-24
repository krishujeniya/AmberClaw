"""DataAgent Data Visualization tool — AI-powered chart generation."""

import json
from typing import Any, Optional
from pydantic import BaseModel, Field

from loguru import logger

from amberclaw.agent.tools.base import PydanticTool


class VizArgs(BaseModel):
    """Arguments for the data_visualize tool."""
    file_path: str = Field(..., description="Path to CSV or Excel file to visualize.")
    instructions: str = Field(..., description="Visualization instructions (e.g. 'scatter plot of age vs salary').")


class DataVizTool(PydanticTool):
    """Generate Plotly visualizations using the DataAgent DataVisualizationAgent."""

    name = "data_visualize"
    description = (
        "Generate Plotly visualizations from a dataset. "
        "Creates scatter plots, bar charts, histograms, line charts, etc. "
        "Returns the visualization as a JSON file path."
    )
    args_schema = VizArgs

    async def run(self, args: VizArgs) -> str:
        try:
            import pandas as pd
            from amberclaw.data.agents import DataVisualizationAgent

            file_path = args.file_path
            df = pd.read_csv(file_path) if not file_path.endswith((".xlsx", ".xls")) else pd.read_excel(file_path)

            agent = DataVisualizationAgent(bypass_recommended_steps=True, bypass_explain_code=True)
            agent.invoke_agent(data_raw=df, user_instructions=args.instructions, max_retries=2)

            plot = agent.get_plotly_graph()
            if plot is not None:
                out_path = file_path.rsplit(".", 1)[0] + "_viz.json"
                with open(out_path, "w") as f:
                    json.dump(plot.to_dict() if hasattr(plot, "to_dict") else plot, f)
                return f"Visualization generated and saved to: {out_path}"

            error = (agent.response or {}).get("data_visualization_error", "Unknown error")
            return f"Visualization failed: {error}"
        except Exception as e:
            logger.error("DataVizTool error: {}", e)
            return f"Error: {e}"
