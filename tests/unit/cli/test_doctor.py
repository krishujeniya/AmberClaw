import pytest
from amberclaw.cli.doctor import run_doctor


def test_run_doctor_execution(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-123456789012345678901234567890123456789012345678")
    run_doctor()
