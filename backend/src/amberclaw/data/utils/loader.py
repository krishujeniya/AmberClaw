"""Data loading utilities for DataAgent tools."""

import pandas as pd


def load_data(path: str) -> pd.DataFrame:
    """Load CSV or Excel into DataFrame."""
    if path.endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    return pd.read_csv(path)
