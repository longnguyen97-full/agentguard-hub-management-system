import json
import logging
import os
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

from app.config import settings
from app.core.db import db
from app.core.registry import registry
from app.core.tracer import tracer

logger = logging.getLogger(__name__)


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BackupManager:
    """
    Unified Data Lifecycle Manager for AgentGuard Dashboard & Langfuse Tracing Stack.
    Provides Backup, Restore, and Reset capabilities with automated rollback protection.
    """

    def __init__(self, backup_dir: Optional[str] = None):
        self.backup_dir = Path(backup_dir or settings.BACKUP_DIR)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.clickhouse_url = "http://127.0.0.1:8123"
        self.clickhouse_auth = ("clickhouse", "clickhouse")
        self.postgres_container = "agent-management-system-postgres-1"

    # =========================================================================
    # Storage Analytics & Health Stats
    # =========================================================================
    def get_storage_stats(self) -> Dict[str, Any]:
        """Returns consolidated storage statistics across Dashboard and Langfuse."""
        dashboard_stats = db.get_storage_stats()

        # Langfuse / ClickHouse Telemetry
        lf_telemetry = tracer.get_langfuse_telemetry()
        clickhouse_events = 0
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.post(
                    self.clickhouse_url,
                    auth=self.clickhouse_auth,
                    content="SELECT count() FROM default.events_core"
                )
                if res.status_code == 200:
                    clickhouse_events = int(res.text.strip() or 0)
        except Exception:
            pass

        # Backups disk usage
        backups = self.list_backups()
        total_backup_bytes = sum(b.get("size_bytes", 0) for b in backups)
        total_backup_formatted = (
            f"{total_backup_bytes / 1024:.1f} KB"
            if total_backup_bytes < 1048576
            else f"{total_backup_bytes / 1048576:.2f} MB"
        )

        return {
            "dashboard": {
                "db_path": dashboard_stats["db_path"],
                "size_bytes": dashboard_stats["size_bytes"],
                "size_formatted": dashboard_stats["size_formatted"],
                "runs_count": dashboard_stats["runs_count"],
                "steps_count": dashboard_stats["steps_count"],
                "memory_runs_count": len(registry.runs),
            },
            "langfuse": {
                "connected": lf_telemetry.get("connected", False),
                "host": lf_telemetry.get("host", settings.LANGFUSE_HOST),
                "version": lf_telemetry.get("version", "v4"),
                "total_traces": lf_telemetry.get("total_traces", 0),
                "total_spans": lf_telemetry.get("total_spans", 0),
                "total_tokens": lf_telemetry.get("total_tokens", 0),
                "total_cost_usd": lf_telemetry.get("total_cost_usd", 0.0),
                "total_cost_vnd": lf_telemetry.get("total_cost_vnd", 0),
                "clickhouse_events_count": clickhouse_events,
            },
            "backups_summary": {
                "total_count": len(backups),
                "total_bytes": total_backup_bytes,
                "total_size_formatted": total_backup_formatted,
                "directory": str(self.backup_dir),
            }
        }

    # =========================================================================
    # Backup Creation
    # =========================================================================
    def create_backup(
        self,
        target: str = "all",
        note: str = "",
        include_langfuse: bool = True
    ) -> Dict[str, Any]:
        """
        Creates a timestamped compressed backup package containing Dashboard SQLite DB,
        human-readable JSON runs export, and Langfuse PostgreSQL/ClickHouse snapshots.
        """
        now = get_utc_now()
        ts_str = now.strftime("%Y%m%d_%H%M%S")
        backup_filename = f"agentguard_backup_{ts_str}.zip"
        backup_filepath = self.backup_dir / backup_filename

        temp_folder = self.backup_dir / f"_tmp_{ts_str}"
        temp_folder.mkdir(parents=True, exist_ok=True)

        dashboard_stats = db.get_storage_stats()
        lf_included = False
        ch_events_count = 0

        try:
            # 1. Backup Dashboard SQLite Database & JSON export
            if target in ["all", "dashboard"]:
                temp_db = temp_folder / "agentguard.db"
                db.backup_to_file(temp_db)

                # Generate JSON export of all runs & steps
                runs = db.load_all_runs()
                runs_json = [r.model_dump(mode="json") for r in runs]
                (temp_folder / "dashboard_runs_export.json").write_text(
                    json.dumps(runs_json, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )

            # 2. Backup Langfuse Tracing Stack
            if (target in ["all", "langfuse"]) and include_langfuse:
                # 2a. Dump PostgreSQL via Docker if available
                pg_dump_sql = self._dump_langfuse_postgres()
                if pg_dump_sql:
                    (temp_folder / "langfuse_postgres.sql").write_text(
                        pg_dump_sql, encoding="utf-8"
                    )
                    lf_included = True

                # 2b. Snapshot ClickHouse traces
                ch_data = self._dump_clickhouse_traces()
                if ch_data:
                    (temp_folder / "langfuse_clickhouse_events.json").write_text(
                        json.dumps(ch_data, ensure_ascii=False, indent=2),
                        encoding="utf-8"
                    )
                    ch_events_count = len(ch_data)
                    lf_included = True

            # 3. Create Manifest
            manifest = {
                "manifest_version": "1.0.0",
                "backup_id": f"bk_{ts_str}",
                "filename": backup_filename,
                "created_at": now.isoformat(),
                "target": target,
                "note": note or "Automated System Backup",
                "dashboard": {
                    "included": target in ["all", "dashboard"],
                    "runs_count": dashboard_stats["runs_count"],
                    "steps_count": dashboard_stats["steps_count"],
                    "db_size_bytes": dashboard_stats["size_bytes"],
                },
                "langfuse": {
                    "included": lf_included,
                    "clickhouse_events": ch_events_count,
                }
            }
            (temp_folder / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            # 4. Create ZIP Archive
            with zipfile.ZipFile(str(backup_filepath), "w", compression=zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(temp_folder):
                    for file in files:
                        full_path = Path(root) / file
                        arcname = full_path.relative_to(temp_folder)
                        zipf.write(full_path, arcname)

            size_bytes = backup_filepath.stat().st_size
            size_formatted = (
                f"{size_bytes / 1024:.1f} KB"
                if size_bytes < 1048576
                else f"{size_bytes / 1048576:.2f} MB"
            )
            manifest["size_bytes"] = size_bytes
            manifest["size_formatted"] = size_formatted

            logger.info(f"Created system backup: {backup_filename} ({size_formatted})")
            return {
                "status": "success",
                "filename": backup_filename,
                "filepath": str(backup_filepath),
                "size_bytes": size_bytes,
                "size_formatted": size_formatted,
                "created_at": now.isoformat(),
                "manifest": manifest,
            }
        finally:
            # Clean up temp working folder
            if temp_folder.exists():
                shutil.rmtree(temp_folder, ignore_errors=True)

    # =========================================================================
    # Backup Listing
    # =========================================================================
    def list_backups(self) -> List[Dict[str, Any]]:
        """Returns all available backups ordered from newest to oldest."""
        backups: List[Dict[str, Any]] = []
        if not self.backup_dir.exists():
            return backups

        for item in self.backup_dir.glob("*.zip"):
            try:
                stat = item.stat()
                size_bytes = stat.st_size
                size_formatted = (
                    f"{size_bytes / 1024:.1f} KB"
                    if size_bytes < 1048576
                    else f"{size_bytes / 1048576:.2f} MB"
                )

                # Attempt to read manifest from ZIP
                manifest: Dict[str, Any] = {}
                try:
                    with zipfile.ZipFile(str(item), "r") as z:
                        if "manifest.json" in z.namelist():
                            manifest_bytes = z.read("manifest.json")
                            manifest = json.loads(manifest_bytes.decode("utf-8"))
                except Exception:
                    pass

                created_at = (
                    manifest.get("created_at")
                    or datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
                )

                backups.append({
                    "filename": item.name,
                    "filepath": str(item),
                    "size_bytes": size_bytes,
                    "size_formatted": size_formatted,
                    "created_at": created_at,
                    "note": manifest.get("note", "System Backup"),
                    "target": manifest.get("target", "all"),
                    "runs_count": manifest.get("dashboard", {}).get("runs_count", 0),
                    "steps_count": manifest.get("dashboard", {}).get("steps_count", 0),
                    "langfuse_included": manifest.get("langfuse", {}).get("included", False),
                })
            except Exception as e:
                logger.warning(f"Failed to inspect backup file {item.name}: {e}")

        # Sort by created_at descending
        backups.sort(key=lambda b: b["created_at"], reverse=True)
        return backups

    # =========================================================================
    # Backup Restoration
    # =========================================================================
    def restore_backup(
        self,
        backup_filename_or_path: str,
        target: str = "all"
    ) -> Dict[str, Any]:
        """
        Restores Dashboard SQLite data and optional Langfuse snapshots from a backup package.
        Automatically creates a safety backup of the active database before replacing it.
        """
        # Resolve path
        path = Path(backup_filename_or_path)
        if not path.is_absolute():
            path = self.backup_dir / backup_filename_or_path

        if not path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_filename_or_path}")

        now = get_utc_now()
        ts_str = now.strftime("%Y%m%d_%H%M%S")

        # SAFETY FIRST: Create automatic safety snapshot of current DB
        pre_restore_backup = self.backup_dir / f"agentguard_auto_pre_restore_{ts_str}.db"
        if db.db_path.exists():
            db.backup_to_file(pre_restore_backup)
            logger.info(f"Created automated safety pre-restore backup: {pre_restore_backup.name}")

        restored_dashboard_runs = 0
        restored_langfuse = False

        temp_folder = self.backup_dir / f"_tmp_restore_{ts_str}"
        temp_folder.mkdir(parents=True, exist_ok=True)

        try:
            # Handle ZIP archive
            if zipfile.is_zipfile(str(path)):
                with zipfile.ZipFile(str(path), "r") as z:
                    z.extractall(temp_folder)

                # 1. Restore Dashboard SQLite DB
                extracted_db = temp_folder / "agentguard.db"
                if target in ["all", "dashboard"] and extracted_db.exists():
                    restored_dashboard_runs = db.restore_from_file(extracted_db)
                    registry.reload_from_db()
                    logger.info(f"Restored {restored_dashboard_runs} agent runs into Dashboard.")

                # 2. Restore Langfuse PostgreSQL dump if included
                extracted_sql = temp_folder / "langfuse_postgres.sql"
                if target in ["all", "langfuse"] and extracted_sql.exists():
                    restored_langfuse = self._restore_langfuse_postgres(
                        extracted_sql.read_text(encoding="utf-8")
                    )

            # Handle direct standalone .db file
            elif path.suffix == ".db":
                if target in ["all", "dashboard"]:
                    restored_dashboard_runs = db.restore_from_file(path)
                    registry.reload_from_db()

            # Broadcast SSE event to update live dashboard Web UI
            registry.broadcast_event({
                "type": "system_data_restored",
                "restored_at": now.isoformat(),
                "runs_count": restored_dashboard_runs,
                "langfuse_restored": restored_langfuse,
            })

            return {
                "status": "success",
                "restored_at": now.isoformat(),
                "restored_runs": restored_dashboard_runs,
                "restored_langfuse": restored_langfuse,
                "pre_restore_backup": pre_restore_backup.name,
                "source_backup": path.name,
            }
        finally:
            if temp_folder.exists():
                shutil.rmtree(temp_folder, ignore_errors=True)

    # =========================================================================
    # Data Reset / Wipe
    # =========================================================================
    def reset_data(
        self,
        target: str = "all",
        preserve_langfuse_auth: bool = True
    ) -> Dict[str, Any]:
        """
        Clears operational data (sessions, steps, ClickHouse telemetry traces).
        Directly purges current database and in-memory state back to 0 without generating backup clutter.
        """
        now = get_utc_now()
        dashboard_deleted_runs = 0
        clickhouse_truncated = False

        # 1. Reset Dashboard SQLite & in-memory state
        if target in ["all", "dashboard"]:
            dashboard_deleted_runs = db.reset_all()
            registry.clear_all()
            logger.info(f"Dashboard reset: {dashboard_deleted_runs} runs cleared.")

        # 2. Reset Langfuse Telemetry Traces in ClickHouse
        if target in ["all", "langfuse"]:
            ch_res = self._truncate_clickhouse()
            clickhouse_truncated = ch_res.get("success", False)
            logger.info(f"ClickHouse trace reset status: {clickhouse_truncated}")

        # Broadcast SSE event to clear browser UI immediately
        registry.broadcast_event({
            "type": "system_data_reset",
            "reset_at": now.isoformat(),
            "target": target,
            "dashboard_deleted_runs": dashboard_deleted_runs,
            "clickhouse_truncated": clickhouse_truncated,
        })

        return {
            "status": "success",
            "reset_at": now.isoformat(),
            "target": target,
            "dashboard_deleted_runs": dashboard_deleted_runs,
            "clickhouse_truncated": clickhouse_truncated,
        }

    # =========================================================================
    # Internal Langfuse & ClickHouse Utilities
    # =========================================================================
    def _dump_langfuse_postgres(self) -> Optional[str]:
        """Exports Langfuse PostgreSQL database via Docker pg_dump."""
        try:
            cmd = ["docker", "exec", self.postgres_container, "pg_dump", "-U", "postgres", "-d", "postgres"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if proc.returncode == 0 and len(proc.stdout) > 200:
                return proc.stdout
        except Exception as e:
            logger.debug(f"pg_dump not available or failed: {e}")
        return None

    def _restore_langfuse_postgres(self, sql_content: str) -> bool:
        """Restores PostgreSQL database via Docker psql."""
        try:
            cmd = ["docker", "exec", "-i", self.postgres_container, "psql", "-U", "postgres", "-d", "postgres"]
            proc = subprocess.run(cmd, input=sql_content, capture_output=True, text=True, timeout=25)
            return proc.returncode == 0
        except Exception as e:
            logger.error(f"Failed to restore PostgreSQL via psql: {e}")
            return False

    def _dump_clickhouse_traces(self) -> List[Dict[str, Any]]:
        """Queries events from ClickHouse for backup."""
        try:
            with httpx.Client(timeout=4.0) as client:
                res = client.post(
                    f"{self.clickhouse_url}/?query=SELECT * FROM default.events_core LIMIT 5000 FORMAT JSON",
                    auth=self.clickhouse_auth
                )
                if res.status_code == 200:
                    return res.json().get("data", [])
        except Exception as e:
            logger.debug(f"ClickHouse dump query error: {e}")
        return []

    def _truncate_clickhouse(self) -> Dict[str, Any]:
        """Truncates high-throughput analytics tables in ClickHouse."""
        tables = [
            "default.events_core",
            "default.traces",
            "default.observations",
            "default.scores",
            "default.analytics_traces",
            "default.analytics_observations",
            "default.analytics_scores",
        ]
        cleared_tables = []
        try:
            with httpx.Client(timeout=4.0) as client:
                for table in tables:
                    try:
                        res = client.post(
                            self.clickhouse_url,
                            auth=self.clickhouse_auth,
                            content=f"TRUNCATE TABLE {table}"
                        )
                        if res.status_code == 200:
                            cleared_tables.append(table)
                    except Exception:
                        pass
            return {"success": len(cleared_tables) > 0, "cleared_tables": cleared_tables}
        except Exception as e:
            logger.error(f"Failed to truncate ClickHouse tables: {e}")
            return {"success": False, "error": str(e)}


backup_manager = BackupManager()

