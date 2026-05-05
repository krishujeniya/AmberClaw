"""
AmberClaw Filesystem Tools (Sandboxed)
"""
from pydantic import BaseModel, Field

from amberclaw.tools.registry import BaseTool


class ReadFileArgs(BaseModel):
    path: str = Field(..., description="The file path to read")


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read the contents of a file. Securely executed within the OS sandbox."
    args_schema = ReadFileArgs

    async def run(self, path: str) -> str:
        if not self.sandbox:
            return "Error: No sandbox available for filesystem operations."
        
        result = await self.sandbox.read_file(path)
        if result.success:
            return result.output
        return f"Error: {result.error}"


class WriteFileArgs(BaseModel):
    path: str = Field(..., description="The file path to write to")
    content: str = Field(..., description="The content to write")


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write content to a file. Securely executed within the OS sandbox."
    args_schema = WriteFileArgs

    async def run(self, path: str, content: str) -> str:
        if not self.sandbox:
            return "Error: No sandbox available for filesystem operations."
        
        result = await self.sandbox.write_file(path, content)
        if result.success:
            return result.output
        return f"Error: {result.error}"


class ListDirArgs(BaseModel):
    path: str = Field(default=".", description="The directory path to list")


class ListDirTool(BaseTool):
    name = "list_dir"
    description = "List the contents of a directory. Securely executed within the OS sandbox."
    args_schema = ListDirArgs

    async def run(self, path: str = ".") -> str:
        if not self.sandbox:
            return "Error: No sandbox available for filesystem operations."
        
        result = await self.sandbox.list_dir(path)
        if result.success:
            return result.output
        return f"Error: {result.error}"
