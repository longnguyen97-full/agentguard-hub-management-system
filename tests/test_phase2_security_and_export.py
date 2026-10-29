import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.registry import registry
from app.main import app
from app.schemas.agent import AgentRunState, AgentRunStatus, AgentStepLog
from agent_sdk import AgentTracker


@pytest.mark.asyncio
async def test_auth_enforcement_and_bypass():
    """Verifies API key protection and open dev mode fallback."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Permissive open mode (settings.API_KEY is None)
        settings.API_KEY = None
        status_resp = await ac.get("/api/agents/auth/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["api_key_required"] is False

        # Open mode allows external start without headers
        resp = await ac.post("/api/agents/external/start", json={
            "agent_name": "OpenModeAgent",
            "prompt": "Test open mode"
        })
        assert resp.status_code == 200
        open_run_id = resp.json()["run_id"]

        # 2. Enforced mode (settings.API_KEY = "secret_key_123")
        settings.API_KEY = "secret_key_123"
        try:
            status_resp = await ac.get("/api/agents/auth/status")
            assert status_resp.json()["api_key_required"] is True

            # Attempting without key fails with 401
            resp_no_key = await ac.post("/api/agents/external/start", json={
                "agent_name": "UnauthorizedAgent",
                "prompt": "Test unauthorized"
            })
            assert resp_no_key.status_code == 401
            assert "Invalid or missing API Key" in resp_no_key.json()["detail"]

            # Attempting with wrong key fails with 401
            resp_wrong_key = await ac.post(
                "/api/agents/external/start",
                json={"agent_name": "WrongKeyAgent", "prompt": "Test"},
                headers={"X-API-Key": "wrong_key"}
            )
            assert resp_wrong_key.status_code == 401

            # Attempting with valid X-API-Key succeeds
            resp_valid_header = await ac.post(
                "/api/agents/external/start",
                json={"agent_name": "AuthAgentHeader", "prompt": "Test"},
                headers={"X-API-Key": "secret_key_123"}
            )
            assert resp_valid_header.status_code == 200

            # Attempting with valid Authorization Bearer succeeds
            resp_valid_bearer = await ac.post(
                "/api/agents/external/start",
                json={"agent_name": "AuthAgentBearer", "prompt": "Test"},
                headers={"Authorization": "Bearer secret_key_123"}
            )
            assert resp_valid_bearer.status_code == 200

            # Sensitive control (kill switch) also requires API Key
            resp_kill_no_key = await ac.post(f"/api/agents/runs/{open_run_id}/kill")
            assert resp_kill_no_key.status_code == 401

            resp_kill_with_key = await ac.post(
                f"/api/agents/runs/{open_run_id}/kill",
                headers={"X-API-Key": "secret_key_123"}
            )
            assert resp_kill_with_key.status_code == 200
        finally:
            # Restore to default permissive mode for other tests
            settings.API_KEY = None


@pytest.mark.asyncio
async def test_audit_export_json_and_csv():
    """Verifies exporting session trace data to structured JSON and tabular CSV."""
    run_id = "test_export_run_001"
    run_state = AgentRunState(
        run_id=run_id,
        agent_name="ExportAuditAgent",
        prompt="Audit analysis task",
        status=AgentRunStatus.COMPLETED,
        max_steps=5,
        current_step=2,
        total_tokens=1500,
        total_cost_usd=0.003,
        total_cost_vnd=76.2,
        steps=[
            AgentStepLog(
                step_number=1,
                thought="Reasoning with LLM",
                action_type="tool_call",
                tool_name="search_db",
                execution_type="llm_reasoning",
                is_billable=True,
                tokens_used=1500,
                cost_usd=0.003,
                cost_vnd=76.2
            ),
            AgentStepLog(
                step_number=2,
                thought="Processing regex match locally",
                action_type="tool_call",
                tool_name="regex_match",
                execution_type="deterministic_tool",
                is_billable=False,
                tokens_used=0,
                cost_usd=0.0,
                cost_vnd=0.0
            )
        ]
    )
    registry.register_run(run_state)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Test JSON Export
        resp_json = await ac.get(f"/api/agents/runs/{run_id}/export?format=json")
        assert resp_json.status_code == 200
        data = resp_json.json()
        assert data["export_metadata"]["run_id"] == run_id
        assert data["cost_and_token_audit"]["billable_steps_count"] == 1
        assert data["cost_and_token_audit"]["deterministic_steps_count"] == 1
        assert data["cost_and_token_audit"]["billable_cost_usd"] == 0.003
        assert len(data["steps"]) == 2

        # Test CSV Export
        resp_csv = await ac.get(f"/api/agents/runs/{run_id}/export?format=csv")
        assert resp_csv.status_code == 200
        assert "text/csv" in resp_csv.headers["content-type"]
        csv_text = resp_csv.text
        assert "run_id,step_number,action_type" in csv_text
        assert "ExportAuditAgent" not in csv_text or run_id in csv_text
        assert "Reasoning with LLM" in csv_text
        assert "Yes" in csv_text  # is_billable
        assert "No (Deterministic/0đ)" in csv_text

        # Test All Runs CSV Export
        resp_all = await ac.get("/api/agents/export/all")
        assert resp_all.status_code == 200
        assert "text/csv" in resp_all.headers["content-type"]
        assert "ExportAuditAgent" in resp_all.text


def test_agent_sdk_with_api_key():
    """Verifies client SDK initializes with optional API key header."""
    tracker_with_key = AgentTracker(endpoint="http://localhost:8000", api_key="my_secret_token")
    assert tracker_with_key.client.headers.get("X-API-Key") == "my_secret_token"

    tracker_no_key = AgentTracker(endpoint="http://localhost:8000")
    assert "X-API-Key" not in tracker_no_key.client.headers

