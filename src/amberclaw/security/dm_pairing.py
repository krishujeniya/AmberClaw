"""DM Pairing security manager for verifying and persisting channel pairing codes."""

import json
import secrets
import time
from pathlib import Path

from loguru import logger

from amberclaw.config.paths import get_data_dir


def get_pairing_file() -> Path:
    """Return the path to the pairing codes file."""
    return get_data_dir() / "pairing_codes.json"


def generate_pairing_code(expires_in_seconds: int = 600) -> str:
    """Generate a secure 6-digit pairing code and save it to pairing_codes.json."""
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    now = time.time()
    expires_at = now + expires_in_seconds

    file_path = get_pairing_file()
    try:
        if file_path.exists():
            data = json.loads(file_path.read_text(encoding="utf-8"))
        else:
            data = {}
    except Exception:
        data = {}

    # Clean up expired codes
    data = {c: val for c, val in data.items() if now <= val.get("expires_at", 0)}

    data[code] = {
        "created_at": now,
        "expires_at": expires_at,
    }

    try:
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error("Failed to write pairing codes: {}", e)

    return code


def verify_and_consume_code(code: str) -> bool:
    """Verify if a pairing code is valid and consume it if so."""
    code = code.strip()
    file_path = get_pairing_file()
    if not file_path.exists():
        return False

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return False

    now = time.time()
    # Clean up expired codes while loading
    data = {c: val for c, val in data.items() if now <= val.get("expires_at", 0)}

    if code not in data:
        # Save cleaned up data back
        try:
            file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass
        return False

    # Valid code! Consume it
    data.pop(code, None)
    try:
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass
    return True
