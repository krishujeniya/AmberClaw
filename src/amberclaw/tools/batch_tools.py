"""
AmberClaw Batch and Interpreter Tools
"""
from pydantic import BaseModel, Field

from amberclaw.security.sandbox import LocalSandbox
from amberclaw.tools.registry import BaseTool, registry


class PythonInterpreterSchema(BaseModel):
    """Schema for the python_interpreter tool."""
    code: str = Field(..., description="The Python code to execute in the secure sandbox")


class PythonInterpreterTool(BaseTool):
    """Tool for executing Python code in a sandbox."""
    
    name = "python_interpreter"
    description = "Execute Python code in a secure sandbox and return the output."
    args_schema = PythonInterpreterSchema

    def __init__(self, sandbox=None):
        self.sandbox = sandbox or LocalSandbox()

    async def run(self, code: str) -> str:
        """Run the code and return results."""
        result = await self.sandbox.execute(code)
        if result.exit_code == 0:
            return result.stdout
        return f"Error (Exit {result.exit_code}): {result.stderr}"

# Auto-register
registry.register(PythonInterpreterTool())
