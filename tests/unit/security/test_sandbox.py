import tempfile
from pathlib import Path

import pytest

from amberclaw.security.landlock import IS_LINUX
from amberclaw.security.sandbox import CodeSandbox


@pytest.mark.asyncio
async def test_sandbox_python_basic_execution() -> None:
    sandbox = CodeSandbox(use_docker=False)
    code = "print('hello from sandbox')"
    result = await sandbox.execute_python(code)
    assert result.exit_code == 0
    assert result.stdout.strip() == "hello from sandbox"
    assert result.stderr == ""

@pytest.mark.asyncio
@pytest.mark.skipif(not IS_LINUX, reason="Linux-specific sandboxing features")
async def test_sandbox_python_blocks_execve() -> None:
    sandbox = CodeSandbox(use_docker=False)
    # This code tries to run a shell command
    code = """
import subprocess
try:
    subprocess.run(["ls"])
    print("success")
except Exception as e:
    print(f"error: {e}")
"""
    result = await sandbox.execute_python(code)
    # The output should show permission denied/errno 13
    assert "Permission denied" in result.stdout or "Permission denied" in result.stderr

@pytest.mark.asyncio
@pytest.mark.skipif(not IS_LINUX, reason="Linux-specific sandboxing features")
async def test_sandbox_python_blocks_outside_workspace_write() -> None:
    # Use a temporary directory as the workspace
    with tempfile.TemporaryDirectory() as ws_dir:
        sandbox = CodeSandbox(use_docker=False, workspace=ws_dir)
        
        # Create an outside temp directory
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as outside_dir:
            outside_file = Path(outside_dir) / "test.txt"
            
            code = f"""
try:
    with open({str(outside_file)!r}, "w") as f:
        f.write("data")
    print("write_success")
except PermissionError:
    print("permission_denied")
except Exception as e:
    print(f"other_error: {{e}}")
"""
            result = await sandbox.execute_python(code)
            assert result.stdout.strip() == "permission_denied"

@pytest.mark.asyncio
async def test_sandbox_bash_execution() -> None:
    sandbox = CodeSandbox(use_docker=False)
    result = await sandbox.execute_bash("echo 'bash execution works'")
    assert result.exit_code == 0
    assert result.stdout.strip() == "bash execution works"
