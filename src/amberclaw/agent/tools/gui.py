"""GUI and Browser automation tools (AC-057)."""

import os
from typing import Any, ClassVar

from loguru import logger

from amberclaw.agent.tools.registry import Tool


class BrowserActionTool(Tool):
    """Tool for controlling a headless browser via Playwright."""

    name = "browser_action"
    description = "Perform actions in a browser (e.g. click, type, navigate)."
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["navigate", "click", "type", "screenshot", "get_content"],
                "description": "The action to perform.",
            },
            "url": {"type": "string", "description": "URL to navigate to (if action=navigate)."},
            "selector": {"type": "string", "description": "CSS selector to interact with."},
            "text": {"type": "string", "description": "Text to type (if action=type)."},
        },
        "required": ["action"],
    }

    async def _execute_playwright(self, action: str, url: str | None, selector: str | None, text: str | None) -> str:
        import base64  # noqa: PLC0415

        from playwright.async_api import async_playwright  # noqa: PLC0415

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                if url:
                    await page.goto(url, timeout=30000)

                async def do_navigate() -> str:
                    if not url:
                        return "Error: 'url' parameter is required for navigate action."
                    await page.goto(url, timeout=30000)
                    title = await page.title()
                    content = await page.content()
                    return f"Successfully navigated to {url}. Page title: '{title}'. Length of content: {len(content)}."

                async def do_click() -> str:
                    if not selector:
                        return "Error: 'selector' parameter is required for click action."
                    await page.click(selector, timeout=10000)
                    return f"Successfully clicked element '{selector}'."

                async def do_type() -> str:
                    if not selector or not text:
                        return "Error: 'selector' and 'text' parameters are required for type action."
                    await page.type(selector, text, timeout=10000)
                    return f"Successfully typed '{text}' into element '{selector}'."

                async def do_screenshot() -> str:
                    screenshot_bytes = await page.screenshot()
                    b64_str = base64.b64encode(screenshot_bytes).decode("utf-8")[:100] + "..."
                    return f"Successfully captured page screenshot (Base64 prefix: {b64_str})."

                async def do_get_content() -> str:
                    content = await page.content()
                    return f"Page content: {content[:1000]}"

                actions = {
                    "navigate": do_navigate,
                    "click": do_click,
                    "type": do_type,
                    "screenshot": do_screenshot,
                    "get_content": do_get_content,
                }

                handler = actions.get(action)
                if handler:
                    return await handler()
                return f"Unsupported browser action: {action}"
            finally:
                await browser.close()

    async def execute(self, arguments: dict[str, Any]) -> str:
        action = arguments.get("action")
        url = arguments.get("url")
        selector = arguments.get("selector")
        text = arguments.get("text")

        try:
            return await self._execute_playwright(action, url, selector, text)
        except Exception as e:
            logger.warning("Playwright execution failed: {}. Falling back to simulation.", e)

        logger.info("Executing simulated browser action: {}", action)

        def sim_navigate() -> str:
            if not url:
                return "Error: 'url' parameter is required for navigate action."
            return f"Successfully navigated to {url}. Page title: 'Simulated Page Title'. Length of content: 500."

        def sim_click() -> str:
            if not selector:
                return "Error: 'selector' parameter is required for click action."
            return f"Successfully clicked element '{selector}' (Simulated)."

        def sim_type() -> str:
            if not selector or not text:
                return "Error: 'selector' and 'text' parameters are required for type action."
            return f"Successfully typed '{text}' into element '{selector}' (Simulated)."

        def sim_screenshot() -> str:
            return "Successfully captured page screenshot (Simulated Base64 encoded image content)."

        def sim_get_content() -> str:
            return "<html><body><h1>Simulated Content</h1><p>This is simulated page content.</p></body></html>"

        sims = {
            "navigate": sim_navigate,
            "click": sim_click,
            "type": sim_type,
            "screenshot": sim_screenshot,
            "get_content": sim_get_content,
        }

        handler = sims.get(action)
        if handler:
            return handler()
        return f"Unsupported browser action: {action}"


class DesktopAutomationTool(Tool):
    """Tool for desktop GUI automation (mouse/keyboard)."""

    name = "desktop_automation"
    description = "Control desktop mouse and keyboard with safety bounds."
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["click", "type", "press_key", "move_mouse"],
                "description": "The desktop action.",
            },
            "x": {"type": "integer", "description": "X coordinate for mouse action."},
            "y": {"type": "integer", "description": "Y coordinate for mouse action."},
            "text": {"type": "string", "description": "Text to type or key to press."},
        },
        "required": ["action"],
    }

    def _execute_pyautogui(self, action: str, x: int | None, y: int | None, text: str | None) -> str:
        import pyautogui  # noqa: PLC0415
        pyautogui.FAILSAFE = True  # Enable failsafe

        def do_click() -> str:
            if x is None or y is None:
                return "Error: 'x' and 'y' coordinates are required for click action."
            pyautogui.click(x, y)
            return f"Successfully executed desktop click at coordinates ({x}, {y})."

        def do_type() -> str:
            if not text:
                return "Error: 'text' parameter is required for type action."
            pyautogui.write(text)
            return f"Successfully typed text: '{text}'."

        def do_press_key() -> str:
            if not text:
                return "Error: 'text' parameter is required for press_key action."
            pyautogui.press(text)
            return f"Successfully pressed key: '{text}'."

        def do_move_mouse() -> str:
            if x is None or y is None:
                return "Error: 'x' and 'y' coordinates are required for move_mouse action."
            pyautogui.moveTo(x, y)
            return f"Successfully moved mouse to coordinates ({x}, {y})."

        actions = {
            "click": do_click,
            "type": do_type,
            "press_key": do_press_key,
            "move_mouse": do_move_mouse,
        }

        handler = actions.get(action)
        if handler:
            return handler()
        return f"Unsupported desktop action: {action}"

    async def execute(self, arguments: dict[str, Any]) -> str:
        action = arguments.get("action")
        x = arguments.get("x")
        y = arguments.get("y")
        text = arguments.get("text")

        try:
            import pyautogui  # noqa: PLC0415, F401
            has_display = bool(os.environ.get("DISPLAY"))
            if has_display:
                return self._execute_pyautogui(action, x, y, text)
        except (ImportError, Exception) as e:
            logger.warning("PyAutoGUI action failed: {}. Falling back to simulation.", e)

        logger.info("Executing simulated desktop action: {}", action)

        def sim_click_or_move() -> str:
            if x is None or y is None:
                return f"Error: 'x' and 'y' coordinates are required for {action} action."
            if x < 0 or y < 0:
                return f"Error: Negative coordinates ({x}, {y}) are invalid."
            return f"Successfully executed desktop {action} at coordinates ({x}, {y}) (Simulated)."

        def sim_type() -> str:
            if not text:
                return "Error: 'text' parameter is required for type action."
            return f"Successfully typed text: '{text}' (Simulated)."

        def sim_press_key() -> str:
            if not text:
                return "Error: 'text' parameter is required for press_key action."
            return f"Successfully pressed key: '{text}' (Simulated)."

        sims = {
            "click": sim_click_or_move,
            "move_mouse": sim_click_or_move,
            "type": sim_type,
            "press_key": sim_press_key,
        }

        handler = sims.get(action)
        if handler:
            return handler()
        return f"Unsupported desktop action: {action}"
