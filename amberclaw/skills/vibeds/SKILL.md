---
name: vibeds
description: "AI-powered data science team — clean, visualize, query, and analyze datasets from the terminal."
metadata: {"amberclaw":{"emoji":"📊","requires":{"pip":["pandas","plotly","scikit-learn"]}}}
---

# VibeDS — AI Data Science Team

Four specialized agents exposed as AmberClaw tools for end-to-end data work.

## Tools

### `vibeds_clean_data`

AI-powered dataset cleaning: missing values, outliers, type conversions, deduplication.

```
Use vibeds_clean_data when a user has a messy CSV/Excel file.
The agent analyzes the data and applies intelligent cleaning automatically.
Output: cleaned CSV file + summary of changes.
```

Parameters:
- `file_path` (required) — Path to CSV or Excel file
- `instructions` (optional) — Custom cleaning instructions

### `vibeds_visualize`

Generate Plotly charts from data using natural language descriptions.

```
Use vibeds_visualize when a user wants charts, plots, or visual analysis.
Describe the desired visualization and the agent generates it.
Output: Plotly JSON file.
```

Parameters:
- `file_path` (required) — Path to data file
- `instructions` (required) — What to visualize (e.g. "scatter plot of age vs income")

### `vibeds_sql_query`

Natural language → SQL query execution on any SQLAlchemy-compatible database.

```
Use vibeds_sql_query when a user wants to query a database without writing SQL.
Supports SQLite, PostgreSQL, MySQL via connection strings.
Output: SQL query + formatted results table.
```

Parameters:
- `connection_string` (required) — SQLAlchemy URI (e.g. `sqlite:///data.db`)
- `instructions` (required) — What to query in plain English

### `vibeds_eda`

Comprehensive exploratory data analysis with statistics, correlations, and insights.

```
Use vibeds_eda when a user wants to understand their data before processing.
Generates summary stats, missing value reports, correlations, distributions.
```

Parameters:
- `file_path` (required) — Path to data file
- `instructions` (optional) — Focus area (e.g. "correlations with target column")

## CLI Commands

- `amberclaw vibeds clean <file>` — Clean a dataset
- `amberclaw vibeds viz <file>` — Visualize data
- `amberclaw vibeds sql <db> <query>` — Query a database

## Configuration

Set in `~/.amberclaw/config.json` under `vibeds`:

```json
{
  "vibeds": {
    "enabled": true,
    "outputDir": "./vibeds_output"
  }
}
```
