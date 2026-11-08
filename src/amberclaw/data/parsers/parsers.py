# BUSINESS SCIENCE UNIVERSITY
# AI DATA SCIENCE TEAM
# ***
# Parsers

from langchain_core.output_parsers import BaseOutputParser

import re


def extract_python_code(text: str) -> str | None:
    python_code_match = re.search(r"```python(.*?)```", text, re.DOTALL)
    if python_code_match:
        return python_code_match.group(1).strip()
    python_code_match = re.search(r"python(.*?)'", text, re.DOTALL)
    if python_code_match:
        return python_code_match.group(1).strip()
    return None


def extract_sql_code(text: str) -> str | None:
    sql_code_match = re.search(r"```sql(.*?)```", text, re.DOTALL)
    sql_code_match_2 = re.search(r"SQLQuery:\s*(.*)", text)
    if sql_code_match:
        return sql_code_match.group(1).strip()
    if sql_code_match_2:
        return sql_code_match_2.group(1).strip()
    sql_code_match = re.search(r"sql(.*?)'", text, re.DOTALL)
    if sql_code_match:
        return sql_code_match.group(1).strip()
    return None


# Python Parser for output standardization
class PythonOutputParser(BaseOutputParser[str]):
    def parse(self, text: str) -> str:
        python_code = extract_python_code(text)
        if python_code is not None:
            return python_code
        return text


# SQL Parser for output standardization
class SQLOutputParser(BaseOutputParser[str]):
    def parse(self, text: str) -> str:
        sql_code = extract_sql_code(text)
        if sql_code is not None:
            return sql_code
        return text
