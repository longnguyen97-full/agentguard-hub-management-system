import asyncio
import pytest
from datetime import datetime
from pathlib import Path
from app.schemas.agent import (
    AgentRunRequest,
    AgentRunState,
    AgentRunStatus,
    AgentStepLog,
    ApprovalDecision,
    get_utc_now,
)
from app.core.db import DatabaseManager
from app.core.alerts import AlertNotifier


@pytest.fixture
def temp_db(tmp_path):
    test_db_path = tmp_path / "test_agentguard.db"
    return DatabaseManager(db_path=str(test_db_path))


def test_sqlite_run_and_step_persistence(temp_db):
    # 1. Create a run state
    run = AgentRunState(
        run_id="run_persist_123",
        agent_name="TestPersistenceBot",
        prompt="Kiểm tra lưu trữ SQLite",
        status=AgentRunStatus.RUNNING,
        max_steps=5,
        total_tokens=100,
        total_cost_usd=0.0001,
        total_cost_vnd=2.54,
    )
    temp_db.save_run(run)

    # 2. Add steps
    step1 = AgentStepLog(
        step_number=1,
        thought="Suy nghĩ bước 1",
        tool_name="test_tool",
        tool_input={"query": "test"},
        tool_output={"result": "ok"},
        tokens_used=50,
        cost_usd=0.00005,
        cost_vnd=1.27,
        is_billable=True,
    )
    temp_db.save_step("run_persist_123", step1)

    # 3. Load all runs
    loaded_runs = temp_db.load_all_runs()
    assert len(loaded_runs) == 1
    loaded_run = loaded_runs[0]
    assert loaded_run.run_id == "run_persist_123"
    assert loaded_run.prompt == "Kiểm tra lưu trữ SQLite"
    assert loaded_run.total_tokens == 100
    assert len(loaded_run.steps) == 1
    assert loaded_run.steps[0].tool_name == "test_tool"

    # 4. Update run to completed
    loaded_run.status = AgentRunStatus.COMPLETED
    loaded_run.final_output = "Hoàn thành tốt"
    temp_db.save_run(loaded_run)

    reloaded = temp_db.load_all_runs()[0]
    assert reloaded.status == AgentRunStatus.COMPLETED
    assert reloaded.final_output == "Hoàn thành tốt"


@pytest.mark.asyncio
async def test_alert_notifier_payload_formatting():
    notifier = AlertNotifier(webhook_url=None)

    # Test Discord formatting
    discord_payload = notifier._format_payload(
        url="https://discord.com/api/webhooks/123/abc",
        title="Emergency Kill Switch",
        message="Agent stopped manually",
        level="CRITICAL",
        metadata={"run_id": "run_999", "operator": "alice"}
    )
    assert "embeds" in discord_payload
    assert discord_payload["embeds"][0]["title"] == "🚨 Emergency Kill Switch"
    assert len(discord_payload["embeds"][0]["fields"]) == 2

    # Test Slack formatting
    slack_payload = notifier._format_payload(
        url="https://hooks.slack.com/services/123/abc",
        title="Approval Required",
        message="Waiting for user decision",
        level="WARNING",
        metadata={"run_id": "run_888"}
    )
    assert "text" in slack_payload
    assert "Approval Required" in slack_payload["text"]

    # Test Generic formatting
    generic_payload = notifier._format_payload(
        url="https://example.com/webhook",
        title="Loop Detected",
        message="Agent loop stopped",
        level="CRITICAL",
        metadata={"run_id": "run_777"}
    )
    assert generic_payload["source"] == "AgentGuard"
    assert generic_payload["level"] == "CRITICAL"

