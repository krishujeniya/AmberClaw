"""Unit tests for GUI and browser automation tools."""

import pytest

from amberclaw.agent.tools.gui import BrowserActionTool, DesktopAutomationTool


@pytest.mark.asyncio
async def test_browser_action_tool_navigate():
    tool = BrowserActionTool()

    # Success navigation
    res = await tool.execute({"action": "navigate", "url": "http://example.com"})
    assert "Successfully navigated to http://example.com" in res

    # Missing URL validation
    res = await tool.execute({"action": "navigate"})
    assert "Error: 'url' parameter is required" in res


@pytest.mark.asyncio
async def test_browser_action_tool_click_and_type():
    tool = BrowserActionTool()

    # Success click
    res = await tool.execute({"action": "click", "selector": "button#submit"})
    assert "Successfully clicked element 'button#submit'" in res

    # Click validation
    res = await tool.execute({"action": "click"})
    assert "Error: 'selector' parameter is required" in res

    # Success type
    res = await tool.execute({"action": "type", "selector": "input#name", "text": "AmberClaw"})
    assert "Successfully typed 'AmberClaw' into element 'input#name'" in res

    # Type validation
    res = await tool.execute({"action": "type", "selector": "input#name"})
    assert "Error: 'selector' and 'text' parameters are required" in res


@pytest.mark.asyncio
async def test_browser_action_tool_screenshot_and_content():
    tool = BrowserActionTool()

    # Screenshot
    res = await tool.execute({"action": "screenshot"})
    assert "Successfully captured page screenshot" in res

    # Content
    res = await tool.execute({"action": "get_content"})
    assert "<html>" in res


@pytest.mark.asyncio
async def test_desktop_automation_tool_clicks():
    tool = DesktopAutomationTool()

    # Success click
    res = await tool.execute({"action": "click", "x": 100, "y": 200})
    assert "Successfully executed desktop click at coordinates (100, 200)" in res

    # Negative coordinate validation
    res = await tool.execute({"action": "click", "x": -50, "y": 100})
    assert "Error: Negative coordinates" in res

    # Missing coordinates validation
    res = await tool.execute({"action": "click", "x": 100})
    assert "Error: 'x' and 'y' coordinates are required" in res


@pytest.mark.asyncio
async def test_desktop_automation_tool_keyboard():
    tool = DesktopAutomationTool()

    # Type action
    res = await tool.execute({"action": "type", "text": "Hello, World!"})
    assert "Successfully typed text: 'Hello, World!'" in res

    # Press key action
    res = await tool.execute({"action": "press_key", "text": "enter"})
    assert "Successfully pressed key: 'enter'" in res

    # Type missing text validation
    res = await tool.execute({"action": "type"})
    assert "Error: 'text' parameter is required" in res
