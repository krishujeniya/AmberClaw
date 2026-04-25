"""DataAgent Data Visualization tool — AI-powered chart generation."""

import json
from pydantic import BaseModel, Field

from loguru import logger

from amberclaw.agent.tools.base import PydanticTool


class VizArgs(BaseModel):
    """Arguments for the data_visualize tool."""

    file_path: str = Field(..., description="Path to CSV or Excel file to visualize.")
    instructions: str = Field(
        ..., description="Visualization instructions (e.g. 'scatter plot of age vs salary')."
    )


class DataVizTool(PydanticTool):
    """Generate Plotly visualizations using the DataAgent DataVisualizationAgent."""

    @property
    def name(self) -> str:
        return "data_visualize"

    @property
    def description(self) -> str:
        return (
            "Generate Plotly visualizations from a dataset. "
            "Creates scatter plots, bar charts, histograms, line charts, etc. "
            "Returns the visualization as a JSON file path."
        )

    @property
    def args_schema(self) -> type[VizArgs]:
        return VizArgs


    async def run(self, args: VizArgs) -> str:
        try:
            import asyncio
            from amberclaw.data.agents import DataVisualizationAgent
            from amberclaw.data.utils.loader import load_data

            file_path = args.file_path
            df = await asyncio.to_thread(load_data, file_path)

            agent = DataVisualizationAgent(bypass_recommended_steps=True, bypass_explain_code=True)
            await asyncio.to_thread(
                agent.invoke_agent, data_raw=df, user_instructions=args.instructions, max_retries=2
            )

            plot = agent.get_plotly_graph()
            if plot is not None:
                out_path = file_path.rsplit(".", 1)[0] + "_viz.json"

                def _save_json(path, data):
                    with open(path, "w") as f:
                        json.dump(data.to_dict() if hasattr(data, "to_dict") else data, f)

                await asyncio.to_thread(_save_json, out_path, plot)
                return f"Visualization generated and saved to: {out_path}"

            error = (agent.response or {}).get("data_visualization_error", "Unknown error")
            return f"Visualization failed: {error}"
        except Exception as e:
            logger.error("DataVizTool error: {}", e)
            return f"Error: {e}"
