"""A plugin connection requires the subprocess pipes it owns."""

from types import SimpleNamespace

import pytest

from amberclaw.plugins.manager import PluginConnection


@pytest.mark.parametrize("missing", ["stdin", "stdout", "stderr"])
def test_connection_rejects_missing_subprocess_pipe(missing):
    pipes = {name: object() for name in ("stdin", "stdout", "stderr")}
    pipes[missing] = None
    with pytest.raises(ValueError, match="pipe"):
        PluginConnection(SimpleNamespace(**pipes), "offline")
