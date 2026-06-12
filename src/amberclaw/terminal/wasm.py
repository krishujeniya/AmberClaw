import asyncio
import logging
import threading
import time
from pathlib import Path
from typing import Any

import micropython_wasm
from micropython_wasm import _define_host_call
from wasmtime import (
    Config,
    Engine,
    ExitTrap,
    Func,
    FuncType,
    Linker,
    Module,
    Store,
    Trap,
    ValType,
    WasiConfig,
)

from amberclaw.terminal.base import BaseTerminalBackend

logger = logging.getLogger(__name__)

OS_SYS_PROXY_PREAMBLE = """
import sys
import os

class OsProxy:
    def __init__(self, original_os):
        self._os = original_os
        class EnvironMock(dict):
            def __getitem__(self, key):
                val = os.getenv(key)
                if val is None: raise KeyError(key)
                return val
            def get(self, key, default=None):
                val = os.getenv(key)
                return val if val is not None else default
            def __setitem__(self, key, value):
                os.putenv(key, str(value))
            def __delitem__(self, key):
                os.unsetenv(key)
        self.environ = EnvironMock()
    def __getattr__(self, name):
        return getattr(self._os, name)

sys.modules["os"] = OsProxy(os)

class SysProxy:
    def __init__(self, original_sys):
        self._sys = original_sys
        self.argv = []
    def __getattr__(self, name):
        return getattr(self._sys, name)

sys.modules["sys"] = SysProxy(sys)
"""

BASH_EMULATOR_TEMPLATE = r"""
import os
import sys

def split_cmd(cmd_str):
    tokens = []
    current = []
    in_double_quote = False
    in_single_quote = False
    i = 0
    n = len(cmd_str)
    while i < n:
        c = cmd_str[i]
        if c == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif c == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif c.isspace() and not in_double_quote and not in_single_quote:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(c)
        i += 1
    if current:
        tokens.append("".join(current))
    return tokens

def main():
    cmd_str = {command_str!r}
    tokens = split_cmd(cmd_str)
    if not tokens:
        sys.exit(0)
    
    cmd = tokens[0]
    args = tokens[1:]
    
    if cmd == "echo":
        print(" ".join(args))
        sys.exit(0)
    elif cmd == "pwd":
        print(os.getcwd())
        sys.exit(0)
    elif cmd == "ls":
        path = args[0] if args else "."
        try:
            for entry in os.listdir(path):
                print(entry)
            sys.exit(0)
        except Exception as e:
            sys.stderr.write("ls: " + str(e) + "\n")
            sys.exit(1)
    elif cmd == "cd":
        if args:
            try:
                os.chdir(args[0])
                sys.exit(0)
            except Exception as e:
                sys.stderr.write("cd: " + str(e) + "\n")
                sys.exit(1)
        sys.exit(0)
    elif cmd == "mkdir":
        if not args:
            sys.stderr.write("mkdir: missing operand\n")
            sys.exit(1)
        recursive = False
        paths = []
        for a in args:
            if a == "-p":
                recursive = True
            else:
                paths.append(a)
        
        for p in paths:
            try:
                if recursive:
                    parts = p.split('/')
                    curr = ""
                    for part in parts:
                        if not part:
                            curr += "/"
                            continue
                        curr = os.path.join(curr, part) if curr else part
                        try:
                            os.mkdir(curr)
                        except OSError:
                            pass
                else:
                    os.mkdir(p)
            except Exception as e:
                sys.stderr.write("mkdir: " + str(e) + "\n")
                sys.exit(1)
        sys.exit(0)
    elif cmd == "rm":
        if not args:
            sys.stderr.write("rm: missing operand\n")
            sys.exit(1)
        for path in args:
            if path in ("-rf", "-f", "-r"):
                continue
            try:
                try:
                    os.remove(path)
                except OSError:
                    os.rmdir(path)
            except Exception as e:
                if "-f" not in args and "-rf" not in args:
                    sys.stderr.write("rm: " + str(e) + "\n")
                    sys.exit(1)
        sys.exit(0)
    elif cmd == "rmdir":
        if not args:
            sys.stderr.write("rmdir: missing operand\n")
            sys.exit(1)
        for path in args:
            try:
                os.rmdir(path)
            except Exception as e:
                sys.stderr.write("rmdir: " + str(e) + "\n")
                sys.exit(1)
        sys.exit(0)
    elif cmd == "cat":
        if not args:
            sys.stderr.write("cat: missing operand\n")
            sys.exit(1)
        for path in args:
            try:
                with open(path, "r") as f:
                    sys.stdout.write(f.read())
            except Exception as e:
                sys.stderr.write("cat: " + str(e) + "\n")
                sys.exit(1)
        sys.exit(0)
    elif cmd == "touch":
        if not args:
            sys.stderr.write("touch: missing operand\n")
            sys.exit(1)
        for path in args:
            try:
                with open(path, "a") as f:
                    pass
            except Exception as e:
                sys.stderr.write("touch: " + str(e) + "\n")
                sys.exit(1)
        sys.exit(0)
    elif cmd == "cp":
        if len(args) < 2:
            sys.stderr.write("cp: missing file operand\n")
            sys.exit(1)
        src, dest = args[0], args[1]
        try:
            try:
                if os.stat(dest)[0] & 0x4000:
                    dest = os.path.join(dest, os.path.basename(src))
            except OSError:
                pass
            with open(src, "rb") as s, open(dest, "wb") as d:
                d.write(s.read())
            sys.exit(0)
        except Exception as e:
            sys.stderr.write("cp: " + str(e) + "\n")
            sys.exit(1)
    elif cmd == "mv":
        if len(args) < 2:
            sys.stderr.write("mv: missing file operand\n")
            sys.exit(1)
        src, dest = args[0], args[1]
        try:
            try:
                if os.stat(dest)[0] & 0x4000:
                    dest = os.path.join(dest, os.path.basename(src))
            except OSError:
                pass
            os.rename(src, dest)
            sys.exit(0)
        except Exception as e:
            sys.stderr.write("mv: " + str(e) + "\n")
            sys.exit(1)
    elif cmd == "python":
        if not args:
            sys.stderr.write("python: interactive mode not supported\n")
            sys.exit(1)
        if args[0] == "-c":
            if len(args) < 2:
                sys.stderr.write("python: option -c requires an argument\n")
                sys.exit(1)
            try:
                exec(args[1], globals())
                sys.exit(0)
            except Exception as e:
                sys.stderr.write("python -c error: " + str(e) + "\n")
                sys.exit(1)
        else:
            script_path = args[0]
            sys.argv = args
            try:
                with open(script_path, "r") as f:
                    exec(f.read(), globals())
                sys.exit(0)
            except Exception as e:
                sys.stderr.write("python script error: " + str(e) + "\n")
                sys.exit(1)
    else:
        sys.stderr.write("bash: " + cmd + ": command not found\n")
        sys.exit(125)

main()
"""


class WasmTerminalBackend(BaseTerminalBackend):
    """WebAssembly execution backend using Wasmtime and MicroPython."""

    def __init__(
        self,
        workspace_dir: str,
        memory_bytes: int = 16 * 1024 * 1024,
        fuel: int = 20_000_000,
        host_result_bytes: int = 256 * 1024,
    ):
        self.workspace_dir = str(Path(workspace_dir).resolve())
        self.memory_bytes = memory_bytes
        self.fuel = fuel
        self.host_result_bytes = host_result_bytes
        self.wasm_path = micropython_wasm.default_wasm_path()

    def _execute_sync(  # noqa: PLR0915
        self,
        code: str,
        timeout: int,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Runs MicroPython WASI in Wasmtime synchronously."""
        start_time = time.perf_counter()

        cfg = Config()
        cfg.consume_fuel = True
        cfg.wasm_exceptions = True
        cfg.max_wasm_stack = 512 * 1024
        cfg.epoch_interruption = True

        engine = Engine(cfg)
        store = Store(engine)
        store.set_limits(
            memory_size=self.memory_bytes,
            instances=1,
            memories=1,
            tables=8,
            table_elements=10_000,
        )
        store.set_fuel(self.fuel)
        store.set_epoch_deadline(1)

        stdout_parts: list[bytes] = []
        stderr_parts: list[bytes] = []

        def capture_stdout(data: bytes) -> None:
            stdout_parts.append(bytes(data))

        def capture_stderr(data: bytes) -> None:
            stderr_parts.append(bytes(data))

        wasi = WasiConfig()
        wasi.argv = ["micropython", "-c", code]
        wasi.env = [(k, v) for k, v in (env or {}).items()]
        wasi.preopen_dir(self.workspace_dir, ".")
        wasi.stdout_custom = capture_stdout
        wasi.stderr_custom = capture_stderr
        store.set_wasi(wasi)

        linker = Linker(engine)
        linker.define_wasi()

        _define_host_call(
            linker,
            store,
            {},
            self.host_result_bytes,
            Func,
            FuncType,
            ValType,
        )

        timer: threading.Timer | None = None
        if timeout > 0:
            timer = threading.Timer(float(timeout), engine.increment_epoch)
            timer.daemon = True
            timer.start()

        exit_code = 0
        try:
            module = Module.from_file(engine, str(self.wasm_path))
            instance = linker.instantiate(store, module)
            start = instance.exports(store).get("_start")
            if not isinstance(start, Func):
                raise RuntimeError("WASI module does not export _start as a function")
            start(store)
        except ExitTrap as exc:
            exit_code = getattr(exc, "code", 0)
            if exit_code is None:
                exit_code = 0
        except Trap as exc:
            exc_str = str(exc)
            if "interrupt" in exc_str or "timeout" in exc_str:
                exit_code = -9
                stderr_parts.append(b"\nTimeout Error: Exceeded limits.")
            elif "fuel" in exc_str:
                exit_code = -9
                stderr_parts.append(b"\nOut of fuel: WebAssembly sandbox execution exceeded resource limits.")
            else:
                exit_code = -1
                stderr_parts.append(f"\nTrap: {exc}".encode(errors="replace"))
        except Exception as exc:
            exit_code = -1
            stderr_parts.append(f"\nExecution error: {exc}".encode(errors="replace"))
        finally:
            if timer is not None:
                timer.cancel()
                timer.join()

        execution_time_ms = (time.perf_counter() - start_time) * 1000

        return {
            "stdout": b"".join(stdout_parts).decode("utf-8", "replace"),
            "stderr": b"".join(stderr_parts).decode("utf-8", "replace"),
            "exit_code": exit_code,
            "execution_time_ms": execution_time_ms,
        }

    async def execute_python(
        self,
        code: str,
        timeout: int = 30,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute Python code in the WASM sandbox."""
        full_code = OS_SYS_PROXY_PREAMBLE + "\n" + code
        return await asyncio.to_thread(self._execute_sync, full_code, timeout, env)

    async def execute_bash(
        self, command: str, timeout: int = 30
    ) -> dict[str, Any]:
        """Execute a bash command emulated inside the WASM sandbox."""
        code = OS_SYS_PROXY_PREAMBLE + "\n" + BASH_EMULATOR_TEMPLATE.format(command_str=command)
        return await asyncio.to_thread(self._execute_sync, code, timeout, None)
