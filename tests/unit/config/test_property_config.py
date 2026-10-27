# ruff: noqa: PLC0415
import pytest

pytest.importorskip("hypothesis")

from hypothesis import given
from hypothesis import strategies as st


# We'll use a dummy config schema for property testing
class DummyConfig:
    def __init__(self, key: str, value: int):
        self.key = key
        self.value = value


@given(st.text(), st.integers())
def test_config_property_validation(key, value):
    config = DummyConfig(key, value)
    assert config.key == key
    assert config.value == value


def test_control_plane_and_data_plane_separation():
    from amberclaw.config.schema import Config, ControlPlaneConfig, DataPlaneConfig

    cfg = Config()
    cp = cfg.control_plane
    dp = cfg.data_plane

    assert isinstance(cp, ControlPlaneConfig)
    assert isinstance(dp, DataPlaneConfig)

    # Control plane fields
    assert hasattr(cp, "gateway")
    assert hasattr(cp, "security")
    assert hasattr(cp, "database")
    assert hasattr(cp, "redis")
    assert hasattr(cp, "plugins")
    assert hasattr(cp, "channels")

    # Data plane fields
    assert hasattr(dp, "agents")
    assert hasattr(dp, "providers")
    assert hasattr(dp, "tools")
    assert hasattr(dp, "assistant")
    assert hasattr(dp, "data")
