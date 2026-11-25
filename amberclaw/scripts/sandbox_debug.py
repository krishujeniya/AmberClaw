import asyncio
import sys
import os
from pathlib import Path
from amberclaw.security.sandbox import CodeSandbox

async def main():
    sandbox = CodeSandbox(use_docker=False)
    code = """
print("Starting child python script...")
import subprocess
try:
    print("Calling subprocess.run...")
    subprocess.run(["ls"])
    print("success")
except Exception as e:
    print(f"error: {e}")
"""
    print("Running execute_python...")
    result = await sandbox.execute_python(code)
    print("exit_code:", result.exit_code)
    print("stdout:", result.stdout)
    print("stderr:", result.stderr)

if __name__ == "__main__":
    asyncio.run(main())
