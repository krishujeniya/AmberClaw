import tempfile
from pathlib import Path

import pytest

from amberclaw.terminal.wasm import WasmTerminalBackend


@pytest.mark.asyncio
async def test_wasm_backend_python_execution() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = WasmTerminalBackend(workspace_dir=tmpdir)
        
        # Test basic python execution
        res = await backend.execute_python("print('hello from wasm python')")
        assert res["exit_code"] == 0
        assert res["stdout"].strip() == "hello from wasm python"
        assert res["stderr"] == ""
        assert res["execution_time_ms"] > 0


@pytest.mark.asyncio
async def test_wasm_backend_env_and_os_environ() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = WasmTerminalBackend(workspace_dir=tmpdir)
        
        # Test environment variables passing and our os.environ proxy patch
        code = """
import os
print("VAL1:", os.getenv("TEST_VAR1"))
print("VAL2:", os.environ.get("TEST_VAR2"))
os.environ["NEW_VAR"] = "shiny"
print("VAL3:", os.environ.get("NEW_VAR"))
"""
        res = await backend.execute_python(
            code,
            env={"TEST_VAR1": "apple", "TEST_VAR2": "banana"},
        )
        assert res["exit_code"] == 0
        stdout = res["stdout"]
        assert "VAL1: apple" in stdout
        assert "VAL2: banana" in stdout
        assert "VAL3: shiny" in stdout


@pytest.mark.asyncio
async def test_wasm_backend_workspace_file_mapping() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = WasmTerminalBackend(workspace_dir=tmpdir)
        
        # Write file from guest python, verify on host
        guest_write = """
with open("guest_file.txt", "w") as f:
    f.write("hello from sandboxed guest")
"""
        res_write = await backend.execute_python(guest_write)
        assert res_write["exit_code"] == 0
        
        host_file = Path(tmpdir) / "guest_file.txt"
        assert host_file.exists()
        assert host_file.read_text() == "hello from sandboxed guest"

        # Write file on host, read from guest python
        host_file.write_text("modified by host")
        guest_read = """
with open("guest_file.txt", "r") as f:
    print(f.read())
"""
        res_read = await backend.execute_python(guest_read)
        assert res_read["exit_code"] == 0
        assert res_read["stdout"].strip() == "modified by host"


@pytest.mark.asyncio
async def test_wasm_backend_timeout_and_out_of_fuel() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Timeout epoch interrupt test
        backend = WasmTerminalBackend(workspace_dir=tmpdir)
        code_infinite = """
import time
for i in range(100):
    time.sleep(0.5)
"""
        # Execute with a 1 second timeout
        res_timeout = await backend.execute_python(code_infinite, timeout=1)
        assert res_timeout["exit_code"] == -9  # noqa: PLR2004
        assert "Timeout Error" in res_timeout["stderr"]

        # 2. Out of fuel test
        backend_low_fuel = WasmTerminalBackend(workspace_dir=tmpdir, fuel=100)
        res_fuel = await backend_low_fuel.execute_python("print('hello')")
        assert res_fuel["exit_code"] == -9  # noqa: PLR2004
        assert "fuel" in res_fuel["stderr"].lower()


@pytest.mark.asyncio
async def test_wasm_backend_bash_emulation() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = WasmTerminalBackend(workspace_dir=tmpdir)
        
        # Test echo
        res = await backend.execute_bash("echo 'hello world'")
        assert res["exit_code"] == 0
        assert res["stdout"].strip() == "hello world"
        
        # Test pwd
        res = await backend.execute_bash("pwd")
        assert res["exit_code"] == 0
        # Guest should print the virtual working directory / workspace path
        
        # Test mkdir and touch
        res = await backend.execute_bash("mkdir test_dir")
        assert res["exit_code"] == 0
        assert (Path(tmpdir) / "test_dir").is_dir()
        
        res = await backend.execute_bash("touch test_dir/file.txt")
        assert res["exit_code"] == 0
        assert (Path(tmpdir) / "test_dir" / "file.txt").is_file()
        
        # Test ls
        res = await backend.execute_bash("ls test_dir")
        assert res["exit_code"] == 0
        assert "file.txt" in res["stdout"]
        
        # Test cp and cat
        res = await backend.execute_bash("cp test_dir/file.txt test_dir/copy.txt")
        assert res["exit_code"] == 0
        assert (Path(tmpdir) / "test_dir" / "copy.txt").is_file()
        
        res = await backend.execute_bash("cat test_dir/copy.txt")
        assert res["exit_code"] == 0
        
        # Test mv
        res = await backend.execute_bash("mv test_dir/copy.txt test_dir/moved.txt")
        assert res["exit_code"] == 0
        assert not (Path(tmpdir) / "test_dir" / "copy.txt").exists()
        assert (Path(tmpdir) / "test_dir" / "moved.txt").is_file()
        
        # Test rm
        res = await backend.execute_bash("rm test_dir/moved.txt")
        assert res["exit_code"] == 0
        assert not (Path(tmpdir) / "test_dir" / "moved.txt").exists()
        
        # Test python command execution inside bash
        res = await backend.execute_bash("python -c \"print('python inside bash')\"")
        assert res["exit_code"] == 0
        assert res["stdout"].strip() == "python inside bash"
        
        # Test script execution
        script_path = Path(tmpdir) / "script.py"
        script_path.write_text("print('script executed')")
        res = await backend.execute_bash("python script.py")
        assert res["exit_code"] == 0
        assert res["stdout"].strip() == "script executed"
        
        # Test command not found
        res = await backend.execute_bash("invalidcmd")
        assert res["exit_code"] == 125  # noqa: PLR2004
        assert "command not found" in res["stderr"]
