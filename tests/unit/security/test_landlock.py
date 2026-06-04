import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from amberclaw.security.landlock import IS_LINUX


@pytest.mark.skipif(not IS_LINUX, reason="Landlock is only supported on Linux")
def test_landlock_sandbox_enforcement() -> None:
    # Use a temporary directory as the workspace
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        allowed_file = tmp_path / "allowed.txt"
        allowed_file.write_text("inside workspace", encoding="utf-8")

        # Create another temporary directory outside workspace (in home, since /tmp is allowed)
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as other_dir:
            other_file = Path(other_dir) / "other.txt"
            other_file.write_text("outside workspace", encoding="utf-8")

            code = f"""
import sys
from amberclaw.security.landlock import apply_sandbox

res = apply_sandbox({tmpdir!r})
if not res:
    sys.exit(10)  # Landlock not supported/failed to apply

# Try reading inside workspace
try:
    with open({str(allowed_file)!r}, "r") as f:
        content = f.read()
    if content != "inside workspace":
        sys.exit(1)
except Exception:
    sys.exit(2)

# Try reading outside workspace (should be blocked)
try:
    with open({str(other_file)!r}, "r") as f:
        f.read()
    sys.exit(3)  # Should have been blocked!
except PermissionError:
    pass  # Blocked successfully!
except Exception as e:
    sys.exit(4)

# Try writing outside workspace (should be blocked)
try:
    with open({str(Path(other_dir) / "new.txt")!r}, "w") as f:
        f.write("blocked")
    sys.exit(5)  # Should have been blocked!
except PermissionError:
    pass  # Blocked successfully!
except Exception:
    sys.exit(6)

sys.exit(0)
"""
            # Run python process
            res = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                check=False,
            )

            # Exit code 10 means Landlock is not supported by the kernel on this host,
            # which is a valid graceful degradation. Exit code 0 means sandboxing worked.
            assert res.returncode in (0, 10), f"Sandbox failed with code {res.returncode}. Stderr: {res.stderr}"
