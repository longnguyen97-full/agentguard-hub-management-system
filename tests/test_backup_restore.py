import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.backup import backup_manager
from app.core.db import db
from app.core.registry import registry
from app.schemas.agent import AgentRunState, AgentRunStatus, get_utc_now


@pytest.mark.asyncio
async def test_backup_and_stats_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test get stats
        res_stats = await client.get("/api/agents/data/stats")
        assert res_stats.status_code == 200
        stats = res_stats.json()
        assert "dashboard" in stats
        assert "langfuse" in stats
        assert "backups_summary" in stats
        assert stats["dashboard"]["runs_count"] >= 0

        # 2. Test create backup
        res_backup = await client.post(
            "/api/agents/data/backup",
            json={"target": "dashboard", "note": "Pytest verification backup", "include_langfuse": False}
        )
        assert res_backup.status_code == 200
        backup_data = res_backup.json()
        assert backup_data["status"] == "success"
        filename = backup_data["filename"]
        assert filename.endswith(".zip")

        # 3. Test list backups
        res_list = await client.get("/api/agents/data/backups")
        assert res_list.status_code == 200
        backups = res_list.json()
        assert any(b["filename"] == filename for b in backups)

        # 4. Test download backup
        res_down = await client.get(f"/api/agents/data/backup/download/{filename}")
        assert res_down.status_code == 200
        assert len(res_down.content) > 0


@pytest.mark.asyncio
async def test_reset_and_restore_cycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Seed a test run
        test_run = AgentRunState(
            run_id="test_run_for_backup",
            agent_name="BackupTester",
            prompt="Run for testing backup and restore",
            status=AgentRunStatus.COMPLETED,
            created_at=get_utc_now(),
            updated_at=get_utc_now()
        )
        registry.register_run(test_run)
        assert registry.get_run("test_run_for_backup") is not None

        # 2. Create backup with this run
        bk_res = await client.post(
            "/api/agents/data/backup",
            json={"target": "dashboard", "note": "Contains test_run_for_backup", "include_langfuse": False}
        )
        assert bk_res.status_code == 200
        bk_file = bk_res.json()["filename"]

        # 3. Reset dashboard data (confirm: True)
        reset_res = await client.post(
            "/api/agents/data/reset",
            json={"confirm": True, "target": "dashboard"}
        )
        assert reset_res.status_code == 200
        assert reset_res.json()["status"] == "success"
        # Verify cleared
        assert registry.get_run("test_run_for_backup") is None
        assert len(registry.runs) == 0

        # 4. Restore from backup
        restore_res = await client.post(
            "/api/agents/data/restore",
            json={"filename": bk_file, "target": "dashboard"}
        )
        assert restore_res.status_code == 200
        assert restore_res.json()["status"] == "success"
        # Verify run was restored
        assert registry.get_run("test_run_for_backup") is not None

