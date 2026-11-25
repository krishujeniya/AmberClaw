"""Pairing authorization must depend on a durable state update."""

from pathlib import Path

import pytest

from amberclaw.security import dm_pairing


def test_failed_consumption_does_not_authorize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dm_pairing, "get_data_dir", lambda: tmp_path)
    code = dm_pairing.generate_pairing_code()

    def fail_write(*_args: object, **_kwargs: object) -> int:
        raise OSError("disk unavailable")

    with monkeypatch.context() as failing_disk:
        failing_disk.setattr(Path, "write_text", fail_write)
        assert not dm_pairing.verify_and_consume_code(code)
    # A failed, denied attempt does not pretend to have removed the code.
    assert dm_pairing.verify_and_consume_code(code)
    assert not dm_pairing.verify_and_consume_code(code)


def test_generation_reports_persistence_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dm_pairing, "get_data_dir", lambda: tmp_path)

    def fail_write(*_args: object, **_kwargs: object) -> int:
        raise OSError("disk unavailable")

    monkeypatch.setattr(Path, "write_text", fail_write)
    with pytest.raises(OSError, match="disk unavailable"):
        dm_pairing.generate_pairing_code()
