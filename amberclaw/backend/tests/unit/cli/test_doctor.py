import pytest

from amberclaw.cli.doctor import run_doctor


@pytest.mark.usefixtures("tmp_path")
def test_run_doctor_execution(monkeypatch):
    monkeypatch.setenv(
        "OPENAI_API_KEY", "sk-123456789012345678901234567890123456789012345678"
    )
    run_doctor()
