"""Channel listing follows the configured Pydantic channel fields."""

import pytest
from typer.testing import CliRunner

from amberclaw.cli.commands import channels
from amberclaw.config.schema import Config


def test_channel_listing_omits_non_channel_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = Config()
    config.channels.telegram.enabled = True
    monkeypatch.setattr(channels.loader, "load_config", lambda: config)
    result = CliRunner().invoke(channels.channels_app, ["list"])
    assert result.exit_code == 0
    assert "Telegram" in result.output
    assert "Enabled" in result.output
    assert "send_progress" not in result.output
    assert "send_tool_hints" not in result.output
