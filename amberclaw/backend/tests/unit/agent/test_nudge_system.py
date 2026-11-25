"""Unit tests for the Memory Nudge System."""

from pathlib import Path

from amberclaw.agent.learning.nudge_system import MemoryNudgeSystem


def test_nudge_system_no_nudge(tmp_path: Path):
    nudge_sys = MemoryNudgeSystem(tmp_path)

    # 3 assistant turns, no pattern keywords
    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "how are you?"},
        {"role": "assistant", "content": "good"},
        {"role": "user", "content": "tell me a joke"},
        {"role": "assistant", "content": "joke"},
    ]

    msg = nudge_sys.should_nudge(history, "what is the weather?")
    assert msg is None


def test_nudge_system_turn_based(tmp_path: Path):
    nudge_sys = MemoryNudgeSystem(tmp_path)

    # 10 assistant turns
    history = []
    for i in range(10):
        history.append({"role": "user", "content": f"msg {i}"})
        history.append({"role": "assistant", "content": f"reply {i}"})

    msg = nudge_sys.should_nudge(history, "hello")
    assert msg is not None
    assert "reached 10 turns" in msg


def test_nudge_system_pattern_based(tmp_path: Path):
    nudge_sys = MemoryNudgeSystem(tmp_path)

    # 3 assistant turns but pattern keywords present in latest message
    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]

    msg1 = nudge_sys.should_nudge(history, "I prefer using python for scripting")
    assert msg1 is not None
    assert "shared a potential preference" in msg1

    msg2 = nudge_sys.should_nudge(history, "Always use ruff for linting my projects")
    assert msg2 is not None
    assert "shared a potential preference" in msg2
