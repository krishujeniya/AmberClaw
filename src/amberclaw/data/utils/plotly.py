
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from plotly.graph_objects import Figure


def plotly_from_dict(plotly_graph_dict: dict[Any, Any] | None) -> Figure | None:
    """
    Convert a Plotly graph dictionary to a Plotly graph object.

    Parameters:
    -----------
    plotly_graph_dict: dict
        A Plotly graph dictionary.

    Returns:
    --------
    plotly_graph: plotly.graph_objs.graph_objs.Figure
        A Plotly graph object.
    """

    if plotly_graph_dict is None:
        return None

    try:
        import plotly.io as pio

        parse_figure: Callable[[str], Figure] = pio.from_json
        return parse_figure(json.dumps(plotly_graph_dict))
    except Exception:
        return None
