"""File system tools: read, write, edit."""

import difflib
from pathlib import Path
from pydantic import BaseModel, Field

from amberclaw.agent.tools.base import PydanticTool


def _resolve_path(
    path: str, workspace: Path | None = None, allowed_dir: Path | None = None
) -> Path:
    """Resolve path against workspace (if relative) and enforce directory restriction."""
    p = Path(path).expanduser()
    if not p.is_absolute() and workspace:
        p = workspace / p
    resolved = p.resolve()

    enforced_dir = allowed_dir or workspace
    if enforced_dir:
        try:
            resolved.relative_to(enforced_dir.resolve())
        except ValueError:
            raise PermissionError(f"Path {path} is outside allowed directory {enforced_dir}")
    return resolved


class ReadFileArgs(BaseModel):
    """Arguments for the read_file tool."""

    path: str = Field(..., description="The file path to read")


class ReadFileTool(PydanticTool):
    """Tool to read file contents."""

    _MAX_CHARS = 128_000  # ~128 KB — prevents OOM from reading huge files into LLM context

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file at the given path."

    @property
    def args_schema(self) -> type[ReadFileArgs]:
        return ReadFileArgs


    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None):
        super().__init__()
        self._workspace = workspace
        self._allowed_dir = allowed_dir

    async def run(self, args: ReadFileArgs) -> str:
        try:
            file_path = _resolve_path(args.path, self._workspace, self._allowed_dir)
            if not file_path.exists():
                return f"Error: File not found: {args.path}"
            if not file_path.is_file():
                return f"Error: Not a file: {args.path}"

            size = file_path.stat().st_size
            if size > self._MAX_CHARS * 4:  # rough upper bound (UTF-8 chars ≤ 4 bytes)
                return (
                    f"Error: File too large ({size:,} bytes). "
                    f"Use exec tool with head/tail/grep to read portions."
                )

            content = file_path.read_text(encoding="utf-8")
            if len(content) > self._MAX_CHARS:
                return (
                    content[: self._MAX_CHARS]
                    + f"\n\n... (truncated — file is {len(content):,} chars, limit {self._MAX_CHARS:,})"
                )
            return content
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error reading file: {str(e)}"


class WriteFileArgs(BaseModel):
    """Arguments for the write_file tool."""

    path: str = Field(..., description="The file path to write to")
    content: str = Field(..., description="The content to write")


class WriteFileTool(PydanticTool):
    """Tool to write content to a file."""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file at the given path. Creates parent directories if needed."

    @property
    def args_schema(self) -> type[WriteFileArgs]:
        return WriteFileArgs


    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None):
        super().__init__()
        self._workspace = workspace
        self._allowed_dir = allowed_dir

    async def run(self, args: WriteFileArgs) -> str:
        try:
            file_path = _resolve_path(args.path, self._workspace, self._allowed_dir)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(args.content, encoding="utf-8")
            return f"Successfully wrote {len(args.content)} bytes to {file_path}"
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error writing file: {str(e)}"


class EditFileArgs(BaseModel):
    """Arguments for the edit_file tool."""

    path: str = Field(..., description="The file path to edit")
    old_text: str = Field(..., description="The exact text to find and replace")
    new_text: str = Field(..., description="The text to replace with")


class EditFileTool(PydanticTool):
    """Tool to edit a file by replacing text."""

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return "Edit a file by replacing old_text with new_text. The old_text must exist exactly in the file."

    @property
    def args_schema(self) -> type[EditFileArgs]:
        return EditFileArgs


    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None):
        super().__init__()
        self._workspace = workspace
        self._allowed_dir = allowed_dir

    async def run(self, args: EditFileArgs) -> str:
        try:
            file_path = _resolve_path(args.path, self._workspace, self._allowed_dir)
            if not file_path.exists():
                return f"Error: File not found: {args.path}"

            content = file_path.read_text(encoding="utf-8")

            if args.old_text not in content:
                return self._not_found_message(args.old_text, content, args.path)

            # Count occurrences
            count = content.count(args.old_text)
            if count > 1:
                return f"Warning: old_text appears {count} times. Please provide more context to make it unique."

            new_content = content.replace(args.old_text, args.new_text, 1)
            file_path.write_text(new_content, encoding="utf-8")

            return f"Successfully edited {file_path}"
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error editing file: {str(e)}"

    @staticmethod
    def _not_found_message(old_text: str, content: str, path: str) -> str:
        """Build a helpful error when old_text is not found."""
        lines = content.splitlines(keepends=True)
        old_lines = old_text.splitlines(keepends=True)
        window = len(old_lines)

        best_ratio, best_start = 0.0, 0
        for i in range(max(1, len(lines) - window + 1)):
            ratio = difflib.SequenceMatcher(None, old_lines, lines[i : i + window]).ratio()
            if ratio > best_ratio:
                best_ratio, best_start = ratio, i

        if best_ratio > 0.5:
            diff = "\n".join(
                difflib.unified_diff(
                    old_lines,
                    lines[best_start : best_start + window],
                    fromfile="old_text (provided)",
                    tofile=f"{path} (actual, line {best_start + 1})",
                    lineterm="",
                )
            )
            return f"Error: old_text not found in {path}.\nBest match ({best_ratio:.0%} similar) at line {best_start + 1}:\n{diff}"
        return (
            f"Error: old_text not found in {path}. No similar text found. Verify the file content."
        )


class ListDirArgs(BaseModel):
    """Arguments for the list_dir tool."""

    path: str = Field(..., description="The directory path to list")


class ListDirTool(PydanticTool):
    """Tool to list directory contents."""

    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return "List the contents of a directory."

    @property
    def args_schema(self) -> type[ListDirArgs]:
        return ListDirArgs


    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None):
        super().__init__()
        self._workspace = workspace
        self._allowed_dir = allowed_dir

    async def run(self, args: ListDirArgs) -> str:
        try:
            dir_path = _resolve_path(args.path, self._workspace, self._allowed_dir)
            if not dir_path.exists():
                return f"Error: Directory not found: {args.path}"
            if not dir_path.is_dir():
                return f"Error: Not a directory: {args.path}"

            items = []
            for item in sorted(dir_path.iterdir()):
                prefix = "📁 " if item.is_dir() else "📄 "
                items.append(f"{prefix}{item.name}")

            if not items:
                return f"Directory {args.path} is empty"

            return "\n".join(items)
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error listing directory: {str(e)}"
