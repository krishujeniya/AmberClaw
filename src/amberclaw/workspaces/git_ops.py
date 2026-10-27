"""Git version control operations localized to workspace roots."""

import shutil
import subprocess

from amberclaw.workspaces.workspace import WorkspaceContext


class GitOps:
    """Provides workspace-scoped Git operations."""

    def __init__(self, context: WorkspaceContext) -> None:
        self.context = context
        self.root_path = context.root_path
        self._git_bin = shutil.which("git") or "git"

    def is_git_repo(self) -> bool:
        """Check if the workspace directory is inside a Git repository."""
        git_dir = self.root_path / ".git"
        return git_dir.exists()

    def get_current_branch(self) -> str | None:
        """Return the active Git branch name, or None if not in a repository."""
        if not self.is_git_repo():
            return None
        try:
            res = subprocess.run(  # noqa: S603
                [self._git_bin, "branch", "--show-current"],
                cwd=self.root_path,
                capture_output=True,
                text=True,
                check=False,
            )
            return res.stdout.strip() if res.returncode == 0 else None
        except Exception:
            return None

    def get_status_short(self) -> str:
        """Return short Git status output."""
        if not self.is_git_repo():
            return "Not a git repository"
        try:
            res = subprocess.run(  # noqa: S603
                [self._git_bin, "status", "--short"],
                cwd=self.root_path,
                capture_output=True,
                text=True,
                check=False,
            )
            return res.stdout.strip() if res.returncode == 0 else "Error retrieving status"
        except Exception as e:
            return f"Error: {e}"

    def init_repository(self) -> bool:
        """Initialize a new Git repository in the workspace root."""
        try:
            res = subprocess.run(  # noqa: S603
                [self._git_bin, "init"],
                cwd=self.root_path,
                capture_output=True,
                text=True,
                check=False,
            )
            return res.returncode == 0
        except Exception:
            return False

    def stage_and_commit(self, message: str, author_name: str = "AmberClaw Agent") -> bool:
        """Stage all workspace changes and create a Git commit."""
        if not self.is_git_repo():
            return False
        try:
            subprocess.run([self._git_bin, "add", "."], cwd=self.root_path, capture_output=True, check=False)  # noqa: S603
            res = subprocess.run(  # noqa: S603
                [self._git_bin, "-c", f"user.name={author_name}", "-c", "user.email=agent@amberclaw.local", "commit", "-m", message],
                cwd=self.root_path,
                capture_output=True,
                text=True,
                check=False,
            )
            return res.returncode == 0
        except Exception:
            return False
