"""DataAgent SQL Database tool — natural language SQL queries."""

from typing import Any
from pydantic import BaseModel, Field

import pandas as pd
from loguru import logger

from amberclaw.agent.tools.base import PydanticTool


class SQLArgs(BaseModel):
    """Arguments for the data_sql_query tool."""

    connection_string: str = Field(
        ..., description="SQLAlchemy connection string (e.g. 'sqlite:///data.db')."
    )
    instructions: str = Field(
        ..., description="What to query (e.g. 'List all customers with >100 orders')."
    )


class DataSQLTool(PydanticTool):
    """Query SQL databases using natural language via DataAgent SQLDatabaseAgent."""

    def __init__(self, model: Any = None):
        self._model = model

    @property
    def name(self) -> str:
        return "data_sql_query"

    @property
    def description(self) -> str:
        return (
            "Query a SQL database using natural language. "
            "Generates and executes SQL queries, returns results as text. "
            "Supports SQLite, PostgreSQL, MySQL."
        )

    @property
    def args_schema(self) -> type[SQLArgs]:
        return SQLArgs


    async def run(self, args: SQLArgs) -> str:
        try:
            import sqlalchemy as sql
            from amberclaw.data.agents import SQLDatabaseAgent

            engine = sql.create_engine(args.connection_string)
            conn = engine.connect()

            agent = SQLDatabaseAgent(
                model=self._model,
                connection=conn,
                bypass_recommended_steps=True,
                bypass_explain_code=True,
            )
            agent.invoke_agent(user_instructions=args.instructions, max_retries=2)

            data = agent.get_data_sql()
            query = agent.get_sql_query_code()

            if data is not None:
                df = pd.DataFrame(data)
                result = f"SQL Query:\n```sql\n{query}\n```\n\nResults ({len(df)} rows):\n{df.head(20).to_markdown(index=False)}"
                if len(df) > 20:
                    result += f"\n\n... and {len(df) - 20} more rows."
                return result

            error = (agent.response or {}).get("sql_database_error", "Unknown error")
            return f"SQL query failed: {error}"
        except Exception as e:
            logger.error("DataSQLTool error: {}", e)
            return f"Error: {e}"

