"""
AmberClaw Batch and Interpreter Tools
"""

from pydantic import BaseModel, Field

from amberclaw.security.sandbox import CodeSandbox
from amberclaw.tools.registry import BaseTool, registry


class PythonInterpreterSchema(BaseModel):
    """Schema for the python_interpreter tool."""

    code: str = Field(
        ..., description="The Python code to execute in the secure sandbox"
    )


class PythonInterpreterTool(BaseTool[[str]]):
    """Tool for executing Python code in a sandbox."""

    name = "python_interpreter"
    description = "Execute Python code in a secure sandbox and return the output."
    args_schema = PythonInterpreterSchema

    def __init__(self, sandbox: CodeSandbox | None = None) -> None:
        super().__init__(sandbox=sandbox)
        self._sandbox = sandbox

    async def run(self, code: str) -> str:
        """Run the code and return results."""
        if self._sandbox is None:
            return "Error: No code sandbox configured."
        result = await self._sandbox.execute_python(code)
        if result.exit_code == 0:
            return result.stdout
        return f"Error (Exit {result.exit_code}): {result.stderr}"


# Auto-register
registry.register(PythonInterpreterTool())
