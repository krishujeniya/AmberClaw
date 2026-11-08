"""WebAuthn challenge entropy must not depend on wall-clock precision."""

from amberclaw.security import mfa


def test_challenges_are_distinct_when_clock_does_not_advance(monkeypatch):
    monkeypatch.setattr(mfa.time, "time", lambda: 1000.0)
    manager = mfa.HardwareMFAManager()
    first = manager.generate_challenge()
    second = manager.generate_challenge()
    assert first != second
    assert first in manager._active_challenges
    assert second in manager._active_challenges
