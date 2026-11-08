"""
AmberClaw Filesystem Tools (Sandboxed)
"""

from typing import ParamSpec, Protocol

from pydantic import BaseModel, Field

from amberclaw.tools.registry import BaseTool


class FilesystemResult(Protocol):
    @property
    def success(self) -> bool: ...
    @property
    def output(self) -> str: ...
    @property
    def error(self) -> str | None: ...


class FilesystemSandbox(Protocol):
    async def read_file(self, path: str) -> FilesystemResult: ...
    async def write_file(self, path: str, content: str) -> FilesystemResult: ...
    async def list_dir(self, path: str) -> FilesystemResult: ...


P = ParamSpec("P")


class FilesystemTool(BaseTool[P]):
    """Typed filesystem capability; callers must supply a confined sandbox."""

    def __init__(self, sandbox: FilesystemSandbox | None = None) -> None:
        super().__init__(sandbox=sandbox)
        self._filesystem_sandbox = sandbox


class ReadFileArgs(BaseModel):
    path: str = Field(..., description="The file path to read")


class ReadFileTool(FilesystemTool[[str]]):
    name = "read_file"
    description = (
        "Read the contents of a file. Securely executed within the OS sandbox."
    )
    args_schema = ReadFileArgs

    async def run(self, path: str) -> str:
        if not self._filesystem_sandbox:
            return "Error: No sandbox available for filesystem operations."

        result = await self._filesystem_sandbox.read_file(path)
        if result.success:
            return result.output
        return f"Error: {result.error}"


class WriteFileArgs(BaseModel):
    path: str = Field(..., description="The file path to write to")
    content: str = Field(..., description="The content to write")


class WriteFileTool(FilesystemTool[[str, str]]):
    name = "write_file"
    description = "Write content to a file. Securely executed within the OS sandbox."
    args_schema = WriteFileArgs

    async def run(self, path: str, content: str) -> str:
        if not self._filesystem_sandbox:
            return "Error: No sandbox available for filesystem operations."

        result = await self._filesystem_sandbox.write_file(path, content)
        if result.success:
            return result.output
        return f"Error: {result.error}"


class ListDirArgs(BaseModel):
    path: str = Field(default=".", description="The directory path to list")


class ListDirTool(FilesystemTool[[str]]):
    name = "list_dir"
    description = (
        "List the contents of a directory. Securely executed within the OS sandbox."
    )
    args_schema = ListDirArgs

    async def run(self, path: str = ".") -> str:
        if not self._filesystem_sandbox:
            return "Error: No sandbox available for filesystem operations."

        result = await self._filesystem_sandbox.list_dir(path)
        if result.success:
            return result.output
        return f"Error: {result.error}"
