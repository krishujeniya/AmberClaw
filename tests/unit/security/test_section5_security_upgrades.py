# ruff: noqa: PLR2004
"""Comprehensive unit and integration tests for Section 5 Zero-Trust Security Stack Upgrades:
- Short-lived access tokens, rotating refresh tokens, and replay detection
- Token and session revocation store
- Hashed API keys with prefix matching, scope enforcement, expiration, and rotation
- Break-glass emergency privilege elevation with audit event generation
- Tool safety approval engine, risk tiers, and runaway loop recursion guards
- Tool capability manifest, strict schema validation, argument sanitization, and output DLP
- API auth router endpoints for token lifecycle and key management
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from amberclaw.api.v1.auth_router import router as auth_router
from amberclaw.security.approval import (
    ApprovalStatus,
    RunawayLoopDetected,
    RunawayLoopGuard,
    ToolApprovalManager,
    ToolRiskLevel,
    ToolSafetyPolicy,
)
from amberclaw.security.filters import (
    ArgumentValidationError,
    ToolCapabilityManifest,
    ToolExecutionFilter,
)
from amberclaw.security.tokens import (
    APIKeyManager,
    BreakGlassManager,
    RefreshTokenManager,
    SecurityCompromiseError,
    TokenRevocationStore,
)


@pytest.fixture(autouse=True)
def clean_security_state():
    """Reset singletons between tests."""
    TokenRevocationStore.get_instance().clear()
    RefreshTokenManager.clear()
    APIKeyManager.get_instance().clear()
    BreakGlassManager.get_instance().clear()
    ToolApprovalManager.get_instance().clear()
    yield
    TokenRevocationStore.get_instance().clear()
    RefreshTokenManager.clear()
    APIKeyManager.get_instance().clear()
    BreakGlassManager.get_instance().clear()
    ToolApprovalManager.get_instance().clear()


# ==============================================================================
# 1. Token Lifecycle, Rotation, & Replay Detection
# ==============================================================================


def test_token_pair_creation_and_payloads():
    mgr = RefreshTokenManager(access_expire_minutes=5, refresh_expire_days=2)
    pair = mgr.create_token_pair(
        user_id="user_123",
        role="operator",
        scopes=["read:agents", "write:agents"],
    )

    assert pair.access_token is not None
    assert pair.refresh_token is not None
    assert pair.expires_in == 300
    assert pair.refresh_expires_in == 172800


def test_refresh_token_rotation_success():
    mgr = RefreshTokenManager()
    initial_pair = mgr.create_token_pair(
        user_id="alice",
        role="admin",
        scopes=["*"],
    )

    # Rotate with valid refresh token
    rotated_pair = mgr.rotate_refresh_token(initial_pair.refresh_token)

    assert rotated_pair.access_token != initial_pair.access_token
    assert rotated_pair.refresh_token != initial_pair.refresh_token

    # Further rotation with new token works
    next_pair = mgr.rotate_refresh_token(rotated_pair.refresh_token)
    assert next_pair.access_token != rotated_pair.access_token


def test_refresh_token_replay_attack_revokes_entire_family():
    mgr = RefreshTokenManager()

    pair_1 = mgr.create_token_pair(user_id="bob", role="user")
    # Legitimate rotation
    pair_2 = mgr.rotate_refresh_token(pair_1.refresh_token)

    # Attacker tries to use pair_1 again (Replay Attack)
    with pytest.raises(SecurityCompromiseError) as exc_info:
        mgr.rotate_refresh_token(pair_1.refresh_token)

    assert "Token reuse detected" in str(exc_info.value)

    # Legitimate user now tries to use pair_2, but whole family is revoked
    with pytest.raises(SecurityCompromiseError) as exc_info2:
        mgr.rotate_refresh_token(pair_2.refresh_token)

    assert "revoked due to prior compromise" in str(exc_info2.value)


def test_token_and_session_revocation():
    mgr = RefreshTokenManager()
    store = TokenRevocationStore.get_instance()

    pair = mgr.create_token_pair(user_id="carol", session_id="sess_xyz")

    # Revoke session
    store.revoke_session("sess_xyz")
    assert store.is_session_revoked("sess_xyz") is True

    # Attempt to rotate should be rejected
    with pytest.raises(PermissionError) as exc_info:
        mgr.rotate_refresh_token(pair.refresh_token)
    assert "has been revoked" in str(exc_info.value)


# ==============================================================================
# 2. Hashed API Key Management
# ==============================================================================


def test_api_key_creation_and_verification():
    mgr = APIKeyManager.get_instance()
    record, raw_key = mgr.create_api_key(
        owner_id="service_agent",
        scopes=["tools:execute", "agents:read"],
        name="Agent Service Key",
        expires_in_days=10,
    )

    assert raw_key.startswith("ak_live_")
    assert record.key_prefix == raw_key[:12]
    assert record.owner_id == "service_agent"
    assert record.hashed_key != raw_key  # Must be hashed!

    # Verify with correct key
    verified = mgr.verify_api_key(raw_key, required_scope="tools:execute")
    assert verified.key_id == record.key_id

    # Verify fails with missing scope
    with pytest.raises(PermissionError) as exc_scope:
        mgr.verify_api_key(raw_key, required_scope="admin:superuser")
    assert "missing required scope" in str(exc_scope.value)


def test_api_key_expiration_and_revocation():
    mgr = APIKeyManager.get_instance()
    # Expired key
    _record, raw_key = mgr.create_api_key(
        owner_id="temp_user",
        expires_in_days=-1,  # Expired yesterday
    )

    with pytest.raises(PermissionError) as exc_exp:
        mgr.verify_api_key(raw_key)
    assert "has expired" in str(exc_exp.value)

    # Active key revoked
    record_active, raw_key_active = mgr.create_api_key(owner_id="active_user")
    assert mgr.verify_api_key(raw_key_active) is not None

    mgr.revoke_api_key(record_active.key_id)
    with pytest.raises(PermissionError):
        mgr.verify_api_key(raw_key_active)


def test_api_key_rotation():
    mgr = APIKeyManager.get_instance()
    old_record, old_raw_key = mgr.create_api_key(
        owner_id="ci_runner",
        scopes=["ci:test"],
        name="CI Key",
    )

    new_record, new_raw_key = mgr.rotate_api_key(old_record.key_id)

    assert new_record.key_id != old_record.key_id
    assert new_raw_key != old_raw_key
    assert new_record.scopes == ["ci:test"]

    # Old key revoked
    with pytest.raises(PermissionError):
        mgr.verify_api_key(old_raw_key)

    # New key works
    assert mgr.verify_api_key(new_raw_key, required_scope="ci:test") is not None


# ==============================================================================
# 3. Break-Glass Emergency Elevation
# ==============================================================================


def test_break_glass_lifecycle():
    bg = BreakGlassManager.get_instance()

    # Reason too short -> rejected
    with pytest.raises(ValueError) as exc_short:
        bg.request_break_glass(user_id="operator_1", reason="too short")
    assert "at least 10 characters" in str(exc_short.value)

    # Valid elevation
    elevation = bg.request_break_glass(
        user_id="operator_1",
        reason="Production incident P0-123 DB outage recovery",
        duration_minutes=30,
    )

    assert elevation.elevation_id.startswith("bg_")
    assert elevation.is_active is True
    assert bg.verify_elevation(elevation.elevation_id) is True

    # Revocation
    bg.revoke_break_glass(elevation.elevation_id, revoked_by="security_team")
    assert bg.verify_elevation(elevation.elevation_id) is False


# ==============================================================================
# 4. Tool & Agent Safety, Risk Tiers, & Runaway Loop Guard
# ==============================================================================


def test_runaway_loop_guard_turn_budget():
    guard = RunawayLoopGuard(max_calls_per_turn=3)

    guard.record_and_check("turn_1", "search_tool", {"q": "1"})
    guard.record_and_check("turn_1", "search_tool", {"q": "2"})
    guard.record_and_check("turn_1", "search_tool", {"q": "3"})

    with pytest.raises(RunawayLoopDetected) as exc_budget:
        guard.record_and_check("turn_1", "search_tool", {"q": "4"})
    assert "exceeded limit of 3 calls" in str(exc_budget.value)


def test_runaway_loop_guard_duplicate_consecutive_calls():
    guard = RunawayLoopGuard(max_calls_per_turn=10, max_duplicate_consecutive_calls=3)

    guard.record_and_check("turn_1", "calc_tool", {"expr": "2+2"})
    guard.record_and_check("turn_1", "calc_tool", {"expr": "2+2"})

    with pytest.raises(RunawayLoopDetected) as exc_dup:
        guard.record_and_check("turn_1", "calc_tool", {"expr": "2+2"})
    assert "3 consecutive times with identical parameters" in str(exc_dup.value)


def test_tool_approval_manager_denylist_and_allowlist():
    policy = ToolSafetyPolicy(
        agent_denylists={"junior_agent": ["shell_exec", "drop_db"]},
        agent_allowlists={"safe_bot": ["read_file", "search"]},
    )
    mgr = ToolApprovalManager(policy=policy)

    # Denylist check
    d1 = mgr.evaluate_tool_execution(
        tool_name="shell_exec",
        agent_id="junior_agent",
        args={},
    )
    assert d1.status == ApprovalStatus.REJECTED
    assert "denylisted" in d1.reason

    # Allowlist check (not allowed)
    d2 = mgr.evaluate_tool_execution(
        tool_name="write_file",
        agent_id="safe_bot",
        args={},
    )
    assert d2.status == ApprovalStatus.REJECTED
    assert "not in allowlist" in d2.reason

    # Allowlist check (allowed)
    d3 = mgr.evaluate_tool_execution(
        tool_name="read_file",
        agent_id="safe_bot",
        args={},
    )
    assert d3.status == ApprovalStatus.APPROVED


def test_tool_approval_manager_human_approval_gate():
    mgr = ToolApprovalManager.get_instance()

    decision = mgr.evaluate_tool_execution(
        tool_name="delete_database",
        agent_id="lead_agent",
        args={"db": "prod"},
        risk_level=ToolRiskLevel.CRITICAL,
    )

    assert decision.status == ApprovalStatus.PENDING_APPROVAL
    assert decision.ticket_id is not None
    assert "requires human approval" in decision.reason

    # Resolve ticket
    assert mgr.resolve_ticket(decision.ticket_id, approved=True) is True


# ==============================================================================
# 5. Tool Capability Manifest, Argument Sanitization, & Output DLP
# ==============================================================================


class SampleToolArgs(BaseModel):
    query: str
    limit: int = 10


def test_tool_execution_filter_argument_validation():
    manifest = ToolCapabilityManifest(
        name="query_tool",
        risk_level=ToolRiskLevel.READ_ONLY,
        is_mutating=False,
        schema_model=SampleToolArgs,
    )

    # Valid args
    clean = ToolExecutionFilter.validate_arguments(
        "query_tool",
        {"query": "amberclaw", "limit": 5},
        manifest=manifest,
        strict_schema=True,
    )
    assert clean["query"] == "amberclaw"
    assert clean["limit"] == 5

    # Path traversal rejected
    with pytest.raises(ArgumentValidationError) as exc_trav:
        ToolExecutionFilter.validate_arguments(
            "query_tool",
            {"query": "../../etc/passwd"},
            manifest=manifest,
        )
    assert "Path traversal pattern detected" in str(exc_trav.value)

    # Strict schema rejects unexpected fields
    with pytest.raises(ArgumentValidationError) as exc_extra:
        ToolExecutionFilter.validate_arguments(
            "query_tool",
            {"query": "search", "unexpected_admin_flag": True},
            manifest=manifest,
            strict_schema=True,
        )
    assert "Unexpected extra fields" in str(exc_extra.value)


def test_tool_execution_filter_output_dlp_and_truncation():
    raw_output = "Secret key: sk-ant-api03-abcdef12345678901234567890\n" + ("A" * 1000)

    filtered = ToolExecutionFilter.filter_output(
        tool_name="test_tool",
        output=raw_output,
        max_output_chars=200,
        redact_sensitive_secrets=True,
    )

    # Secret must be redacted
    assert "sk-ant-api03" not in filtered
    assert "[REDACTED_SECRET]" in filtered
    # Must be truncated
    assert "[TRUNCATED:" in filtered
    assert len(filtered) < 400


# ==============================================================================
# 6. Auth API Endpoints (FastAPI TestClient)
# ==============================================================================


@pytest.fixture
def auth_client():
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1/auth")
    return TestClient(app)


def test_api_auth_token_refresh_and_revoke_endpoints(auth_client):
    # 1. Login to obtain tokens
    res = auth_client.post(
        "/api/v1/auth/token",
        json={"client_id": "admin", "client_secret": "amberclaw-secret"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data

    # 2. Refresh token
    refresh_res = auth_client.post(
        "/api/v1/auth/token/refresh",
        json={"refresh_token": data["refresh_token"]},
    )
    assert refresh_res.status_code == 200
    refreshed_data = refresh_res.json()
    assert refreshed_data["access_token"] != data["access_token"]

    # 3. Revoke
    revoke_res = auth_client.post(
        "/api/v1/auth/token/revoke",
        json={"jti": "some_jti", "session_id": "sess_123"},
    )
    assert revoke_res.status_code == 200


def test_api_auth_api_keys_and_break_glass_endpoints(auth_client):
    # 1. Create API Key
    res_key = auth_client.post(
        "/api/v1/auth/api-keys",
        json={
            "owner_id": "api_test_user",
            "scopes": ["agents:read", "tools:call"],
            "name": "Integration Test Key",
        },
    )
    assert res_key.status_code == 201
    key_data = res_key.json()
    assert key_data["raw_key"].startswith("ak_live_")
    key_id = key_data["key_id"]

    # 2. Rotate API Key
    res_rot = auth_client.post(
        "/api/v1/auth/api-keys/rotate",
        json={"key_id": key_id},
    )
    assert res_rot.status_code == 200
    rotated_data = res_rot.json()
    assert rotated_data["raw_key"] != key_data["raw_key"]

    # 3. Break-Glass Emergency Elevation
    res_bg = auth_client.post(
        "/api/v1/auth/auth/break-glass",
        json={
            "user_id": "oncall_engineer",
            "reason": "Emergency DB recovery and cache restart",
            "duration_minutes": 45,
        },
    )
    assert res_bg.status_code == 200
    bg_data = res_bg.json()
    assert bg_data["elevation_id"].startswith("bg_")
    assert bg_data["is_active"] is True
