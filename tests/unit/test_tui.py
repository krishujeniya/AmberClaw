# ruff: noqa: PLR2004
"""Unit tests for AmberClaw Rich Terminal User Interface (TUI)."""

from rich.layout import Layout
from rich.panel import Panel

from amberclaw.tui.app import AmberClawTUIApp
from amberclaw.tui.completion import CommandPalette
from amberclaw.tui.input import TUIInputHandler
from amberclaw.tui.renderer import TUIMessage, TUIRenderer
from amberclaw.tui.status import (
    TUIStatusState,
    render_inspector_card,
    render_status_bar,
)
from amberclaw.tui.themes import DefaultTheme, OceanTheme, get_theme


def test_tui_themes():
    default_th = get_theme("default")
    assert default_th.name == "default"
    assert default_th.primary == DefaultTheme.primary

    light_th = get_theme("light")
    assert light_th.name == "light"
    assert light_th.text == "black"

    ocean_th = get_theme("ocean")
    assert ocean_th.name == "ocean"
    assert ocean_th.background == OceanTheme.background

    # Fallback to default
    fallback_th = get_theme("nonexistent_theme_xyz")
    assert fallback_th.name == "default"


def test_status_bar_and_inspector_rendering():
    state = TUIStatusState(
        model="claude-3-5-sonnet",
        session_id="session_42",
        provider="anthropic",
        total_tokens=1500,
        active_sandbox="docker",
        pending_approvals=2,
        is_streaming=True,
    )

    status_panel = render_status_bar(state, DefaultTheme)
    assert isinstance(status_panel, Panel)

    inspector_panel = render_inspector_card(state, DefaultTheme)
    assert isinstance(inspector_panel, Panel)


def test_message_and_timeline_rendering():
    renderer = TUIRenderer(theme=DefaultTheme)

    # 1. User message
    user_msg = TUIMessage(role="user", content="Deploy the app")
    user_panel = renderer.render_message(user_msg)
    assert isinstance(user_panel, Panel)

    # 2. Assistant Markdown message
    asst_msg = TUIMessage(
        role="assistant", content="### Plan\n- Step 1: Build\n- Step 2: Push"
    )
    asst_panel = renderer.render_message(asst_msg)
    assert isinstance(asst_panel, Panel)

    # 3. Thought
    thought_msg = TUIMessage(
        role="assistant", content="Reflecting on requirements...", is_thought=True
    )
    thought_panel = renderer.render_message(thought_msg)
    assert isinstance(thought_panel, Panel)

    # 4. Tool Execution Card
    tool_msg = TUIMessage(
        role="tool",
        tool_name="shell_exec",
        tool_args={"command": "ls -la"},
        tool_output='{"status": "ok", "files": ["main.py"]}',
    )
    tool_panel = renderer.render_message(tool_msg)
    assert isinstance(tool_panel, Panel)

    # 5. Approval Prompt
    approval_msg = TUIMessage(
        role="system",
        content="Delete production database",
        is_approval_request=True,
        approval_ticket_id="TICKET_001",
        tool_name="rm -rf /prod/db",
    )
    approval_panel = renderer.render_message(approval_msg)
    assert isinstance(approval_panel, Panel)

    # 6. Timeline group
    timeline = renderer.render_timeline([user_msg, asst_msg, tool_msg, approval_msg])
    assert len(timeline.renderables) == 4


def test_command_palette_and_suggestions():
    palette = CommandPalette()

    # Prefix suggestions
    matches = palette.suggest("/m")
    names = [m.name for m in matches]
    assert "/model" in names

    # Unknown prefix
    assert len(palette.suggest("/xyznonexistent")) == 0

    # Non slash prefix
    assert len(palette.suggest("hello")) == 0

    # Parsing commands with arguments
    parsed = palette.parse_command("/model gpt-4o-mini")
    assert parsed is not None
    assert parsed[0] == "/model"
    assert parsed[1] == ["gpt-4o-mini"]

    # Alias parsing
    parsed_alias = palette.parse_command("/quit")
    assert parsed_alias is not None
    assert parsed_alias[0] == "/exit"


def test_input_handler_and_history():
    handler = TUIInputHandler(max_history=3)

    res_empty = handler.process_input("   ")
    assert res_empty.type == "empty"

    res_chat = handler.process_input("Hello agent!")
    assert res_chat.type == "chat"
    assert res_chat.raw_text == "Hello agent!"
    assert len(handler.history) == 1

    res_cmd = handler.process_input("/theme ocean")
    assert res_cmd.type == "command"
    assert res_cmd.command == "/theme"
    assert res_cmd.args == ["ocean"]

    handler.process_input("msg 2")
    handler.process_input("msg 3")
    # Max history should bound length
    assert len(handler.history) <= 3


def test_tui_app_layout_and_commands():
    app = AmberClawTUIApp(theme_name="default")

    # Add messages
    app.add_user_message("Check system")
    app.add_tool_event(
        "doctor_check", tool_args={"all": True}, tool_output="All systems green"
    )
    app.add_assistant_message("System is fully operational.")
    app.add_approval_request("TCK_99", "Reboot Node", "Cluster node 3 reboot required")

    assert len(app.messages) == 4
    assert app.state.pending_approvals == 1

    # Build split pane layout
    layout = app.build_layout()
    assert isinstance(layout, Layout)
    assert layout.get("header") is not None
    assert layout.get("body") is not None
    assert layout.get("footer") is not None
    assert layout.get("chat") is not None
    assert layout.get("inspector") is not None

    # Execute TUI commands
    res_help = app.process_command(app.input_handler.process_input("/help"))
    assert "Available Commands" in res_help

    res_theme = app.process_command(app.input_handler.process_input("/theme ocean"))
    assert "ocean" in res_theme
    assert app.theme.name == "ocean"

    res_model = app.process_command(app.input_handler.process_input("/model o3-mini"))
    assert "o3-mini" in res_model
    assert app.state.model == "o3-mini"

    res_session = app.process_command(
        app.input_handler.process_input("/session debug_sess")
    )
    assert "debug_sess" in res_session
    assert app.state.session_id == "debug_sess"

    res_clear = app.process_command(app.input_handler.process_input("/clear"))
    assert "cleared" in res_clear
    assert len(app.messages) == 0

    res_exit = app.process_command(app.input_handler.process_input("/exit"))
    assert res_exit == "EXIT"


def test_tui_no_color_theme_and_resize(monkeypatch):
    # Test NO_COLOR environment variable adherence
    monkeypatch.setenv("NO_COLOR", "1")
    nc_theme = get_theme("default")
    assert nc_theme.name == "no-color"

    monkeypatch.delenv("NO_COLOR", raising=False)
    reg_nc_theme = get_theme("no-color")
    assert reg_nc_theme.name == "no-color"
    assert reg_nc_theme.primary == "default"

    # Terminal resize handling (SSH, Windows Terminal, low-geometry)
    app = AmberClawTUIApp(theme_name="no-color")
    app.handle_resize(width=80, height=24)
    assert app.console.width == 80
    assert app.console.height == 24

    # Narrow terminal resize protection
    app.handle_resize(width=10, height=5)
    assert app.console.width >= 20
    assert app.console.height >= 10


def test_tui_skills_and_governance_commands():
    app = AmberClawTUIApp()
    app.state.pending_approvals = 2

    res_skills = app.process_command(app.input_handler.process_input("/skills"))
    assert "Active Skills" in res_skills

    res_approve = app.process_command(
        app.input_handler.process_input("/approve TICK_42")
    )
    assert "approved" in res_approve
    assert app.state.pending_approvals == 1

    res_reject = app.process_command(app.input_handler.process_input("/reject TICK_43"))
    assert "rejected" in res_reject
    assert app.state.pending_approvals == 0

    res_doctor = app.process_command(app.input_handler.process_input("/doctor"))
    assert "Doctor Diagnostic" in res_doctor
