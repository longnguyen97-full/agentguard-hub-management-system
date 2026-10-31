import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.registry import registry
from app.schemas.agent import AgentRunStatus


@pytest.mark.asyncio
async def test_external_agent_ingestion_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Start run
        start_resp = await client.post(
            "/api/agents/external/start",
            json={
                "agent_name": "TestExternalBot",
                "prompt": "Test external task",
                "max_steps": 5
            }
        )
        assert start_resp.status_code == 200
        data = start_resp.json()
        run_id = data["run_id"]
        assert run_id.startswith("ext_")

        # 2. Post step
        step_resp = await client.post(
            f"/api/agents/external/{run_id}/step",
            json={
                "step_number": 1,
                "thought": "Thinking step 1",
                "tool_name": "search_db",
                "tool_input": {"q": "user"},
                "tool_output": {"found": True},
                "tokens_used": 150,
                "cost_usd": 0.0001,
                "is_billable": True
            }
        )
        assert step_resp.status_code == 200

        # Check state in registry
        run_state = registry.get_run(run_id)
        assert run_state is not None
        assert run_state.current_step == 1
        assert run_state.total_tokens == 150
        assert len(run_state.steps) == 1

        # 3. Finish run
        finish_resp = await client.post(
            f"/api/agents/external/{run_id}/finish",
            json={
                "status": "COMPLETED",
                "final_output": "Task completed successfully"
            }
        )
        assert finish_resp.status_code == 200
        assert run_state.status == AgentRunStatus.COMPLETED
        assert run_state.final_output == "Task completed successfully"


@pytest.mark.asyncio
async def test_external_agent_auto_model_pricing_and_billable():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        start_resp = await client.post(
            "/api/agents/external/start",
            json={
                "agent_name": "telegram-gemini-bot",
                "prompt": "bạn là ai",
                "max_steps": 5
            }
        )
        assert start_resp.status_code == 200
        run_id = start_resp.json()["run_id"]

        # Post step simulating telegram bot sending gemini as tool_name without cost
        step_resp = await client.post(
            f"/api/agents/external/{run_id}/step",
            json={
                "step_number": 1,
                "tool_name": "gemini-2.5-flash",
                "tokens_used": 96,
                "cost_usd": 0.0
            }
        )
        assert step_resp.status_code == 200

        run_state = registry.get_run(run_id)
        assert run_state is not None
        assert run_state.total_tokens == 96
        # Must auto-calculate non-zero cost and set is_billable
        assert run_state.total_cost_usd > 0.0
        assert run_state.total_cost_vnd > 0.0
        assert run_state.steps[0].is_billable is True
        assert run_state.steps[0].cost_usd > 0.0

