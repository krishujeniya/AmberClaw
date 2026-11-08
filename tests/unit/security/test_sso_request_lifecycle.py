"""Pending login expiry and configuration invalidation must fail closed."""

from types import SimpleNamespace

import pytest

from amberclaw.api.v1.sso_router import _requests, set_sso_config
from amberclaw.security.sso import requests
from amberclaw.security.sso.models import SSOConfig


def test_pending_login_expires_and_cannot_be_reused(monkeypatch):
    store = requests.LoginRequests()
    state, login = store.create(SSOConfig())
    monkeypatch.setattr(
        requests, "time", SimpleNamespace(monotonic=lambda: login.expires + 1)
    )
    with pytest.raises(ValueError, match="expired"):
        store.consume(state, state)
    with pytest.raises(ValueError, match="consumed"):
        store.consume(state, state)


def test_pending_login_limit_and_config_snapshot(monkeypatch):
    monkeypatch.setattr(requests, "MAX_PENDING_LOGINS", 1)
    config = SSOConfig()
    store = requests.LoginRequests()
    state, login = store.create(config)
    config.default_role = "admin"
    assert login.config.default_role == "user"
    with pytest.raises(ValueError, match="Too many"):
        store.create(config)
    assert store.consume(state, state) is login
    store.create(config)


def test_configuration_change_invalidates_pending_logins():
    state, _ = _requests.create(SSOConfig())
    set_sso_config(SSOConfig(enabled=False))
    with pytest.raises(ValueError, match="consumed"):
        _requests.consume(state, state)
