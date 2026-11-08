---
name: data
description: "AI-powered data science team — clean, visualize, query, and analyze datasets from the terminal."
metadata: {"amberclaw":{"emoji":"📊","requires":{"pip":["pandas","plotly","scikit-learn"]}}}
---

# Data Intelligence — AI Data Science Team

Four specialized agents exposed as AmberClaw tools for end-to-end data work.

## Tools

### `data_clean_data`

AI-powered dataset cleaning: missing values, outliers, type conversions, deduplication.

```
Use data_clean_data when a user has a messy CSV/Excel file.
The agent analyzes the data and applies intelligent cleaning automatically.
Output: cleaned CSV file + summary of changes.
```

Parameters:
- `file_path` (required) — Path to CSV or Excel file
- `instructions` (optional) — Custom cleaning instructions

### `data_visualize`

Generate Plotly charts from data using natural language descriptions.

```
Use data_visualize when a user wants charts, plots, or visual analysis.
Describe the desired visualization and the agent generates it.
Output: Plotly JSON file.
```

Parameters:
- `file_path` (required) — Path to data file
- `instructions` (required) — What to visualize (e.g. "scatter plot of age vs income")

### `data_sql_query`

Natural language → SQL query execution on any SQLAlchemy-compatible database.

```
Use data_sql_query when a user wants to query a database without writing SQL.
Supports SQLite, PostgreSQL, MySQL via connection strings.
Output: SQL query + formatted results table.
```

Parameters:
- `connection_string` (required) — SQLAlchemy URI (e.g. `sqlite:///data.db`)
- `instructions` (required) — What to query in plain English

### `data_eda`

Comprehensive exploratory data analysis with statistics, correlations, and insights.

```
Use data_eda when a user wants to understand their data before processing.
Generates summary stats, missing value reports, correlations, distributions.
```

Parameters:
- `file_path` (required) — Path to data file
- `instructions` (optional) — Focus area (e.g. "correlations with target column")

## CLI Commands

- `amberclaw data clean <file>` — Clean a dataset
- `amberclaw data viz <file>` — Visualize data
- `amberclaw data sql <db> <query>` — Query a database

## Configuration

Set in `~/.amberclaw/config.json` under `data`:

```json
{
  "data": {
    "enabled": true,
    "outputDir": "./data_output"
  }
}
```
