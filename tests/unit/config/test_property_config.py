import pytest
from hypothesis import given, strategies as st

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
