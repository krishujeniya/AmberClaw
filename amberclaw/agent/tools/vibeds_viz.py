"""VibeDS Data Visualization tool — AI-powered chart generation."""

import json
from typing import Any

from loguru import logger

from amberclaw.agent.tools.base import Tool


class VibeDataVizTool(Tool):
    """Generate Plotly visualizations using the VibeDS DataVisualizationAgent."""

    name = "vibeds_visualize"
    description = (
        "Generate Plotly visualizations from a dataset. "
        "Creates scatter plots, bar charts, histograms, line charts, etc. "
        "Returns the visualization as a JSON file path."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to CSV or Excel file to visualize.",
            },
            "instructions": {
                "type": "string",
                "description": "Visualization instructions (e.g. 'scatter plot of age vs salary').",
            },
        },
        "required": ["file_path", "instructions"],
    }

    async def execute(self, file_path: str, instructions: str, **kwargs: Any) -> str:
        try:
            import pandas as pd
            from amberclaw.vibeds.agents import DataVisualizationAgent

            df = pd.read_csv(file_path) if not file_path.endswith((".xlsx", ".xls")) else pd.read_excel(file_path)

            agent = DataVisualizationAgent(bypass_recommended_steps=True, bypass_explain_code=True)
            agent.invoke_agent(data_raw=df, user_instructions=instructions, max_retries=2)

            plot = agent.get_plotly_graph()
            if plot is not None:
                out_path = file_path.rsplit(".", 1)[0] + "_viz.json"
                with open(out_path, "w") as f:
                    json.dump(plot.to_dict() if hasattr(plot, "to_dict") else plot, f)
                return f"Visualization generated and saved to: {out_path}"

            error = (agent.response or {}).get("data_visualization_error", "Unknown error")
            return f"Visualization failed: {error}"
        except Exception as e:
            logger.error("VibeDataVizTool error: {}", e)
            return f"Error: {e}"
