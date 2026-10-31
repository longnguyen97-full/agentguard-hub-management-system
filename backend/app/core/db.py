import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from app.config import settings
from app.schemas.agent import (
    AgentRunState,
    AgentRunStatus,
    AgentStepLog,
    ToolApprovalRequest,
    get_utc_now,
)

logger = logging.getLogger(__name__)


class DatabaseManager:
    """SQLite persistence manager for Agent runs, steps, and telemetry."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or settings.DATABASE_PATH)
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Creates tables and indexes if they do not exist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS agent_runs (
                        run_id TEXT PRIMARY KEY,
                        agent_name TEXT NOT NULL,
                        prompt TEXT NOT NULL,
                        status TEXT NOT NULL,
                        current_step INTEGER DEFAULT 0,
                        max_steps INTEGER DEFAULT 10,
                        total_tokens INTEGER DEFAULT 0,
                        total_cost_usd REAL DEFAULT 0.0,
                        total_cost_vnd REAL DEFAULT 0.0,
                        is_simulation INTEGER DEFAULT 0,
                        final_output TEXT,
                        error_message TEXT,
                        pending_approval TEXT,
                        langfuse_trace_id TEXT,
                        langfuse_trace_url TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS agent_steps (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT NOT NULL,
                        step_number INTEGER NOT NULL,
                        thought TEXT,
                        action_type TEXT,
                        tool_name TEXT,
                        tool_input TEXT,
                        tool_output TEXT,
                        latency_ms REAL DEFAULT 0.0,
                        tokens_used INTEGER DEFAULT 0,
                        cost_usd REAL DEFAULT 0.0,
                        cost_vnd REAL DEFAULT 0.0,
                        is_billable INTEGER DEFAULT 1,
                        execution_type TEXT DEFAULT 'llm_reasoning',
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE
                    )
                """)

                cursor.execute("CREATE INDEX IF NOT EXISTS idx_steps_run_id ON agent_steps(run_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_created_at ON agent_runs(created_at DESC)")
                conn.commit()
            logger.info(f"AgentGuard SQLite persistence initialized at: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite database: {e}")

    def save_run(self, run: AgentRunState):
        """Inserts or updates an agent run state."""
        try:
            pending_json = run.pending_approval.model_dump_json() if run.pending_approval else None
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO agent_runs (
                        run_id, agent_name, prompt, status, current_step, max_steps,
                        total_tokens, total_cost_usd, total_cost_vnd, is_simulation,
                        final_output, error_message, pending_approval, langfuse_trace_id,
                        langfuse_trace_url, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id) DO UPDATE SET
                        status = excluded.status,
                        current_step = excluded.current_step,
                        total_tokens = excluded.total_tokens,
                        total_cost_usd = excluded.total_cost_usd,
                        total_cost_vnd = excluded.total_cost_vnd,
                        final_output = excluded.final_output,
                        error_message = excluded.error_message,
                        pending_approval = excluded.pending_approval,
                        updated_at = excluded.updated_at
                """, (
                    run.run_id,
                    run.agent_name,
                    run.prompt,
                    run.status.value if isinstance(run.status, AgentRunStatus) else str(run.status),
                    run.current_step,
                    run.max_steps,
                    run.total_tokens,
                    run.total_cost_usd,
                    run.total_cost_vnd,
                    1 if getattr(run, "is_simulation", False) else 0,
                    run.final_output,
                    run.error_message,
                    pending_json,
                    run.langfuse_trace_id,
                    run.langfuse_trace_url,
                    run.created_at.isoformat() if isinstance(run.created_at, datetime) else str(run.created_at),
                    run.updated_at.isoformat() if isinstance(run.updated_at, datetime) else str(run.updated_at),
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save run {run.run_id} to DB: {e}")

    def save_step(self, run_id: str, step: AgentStepLog):
        """Appends a completed step log to the database."""
        try:
            tool_input_json = json.dumps(step.tool_input, ensure_ascii=False) if step.tool_input is not None else None
            tool_output_str = json.dumps(step.tool_output, ensure_ascii=False) if isinstance(step.tool_output, (dict, list)) else (str(step.tool_output) if step.tool_output is not None else None)

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO agent_steps (
                        run_id, step_number, thought, action_type, tool_name,
                        tool_input, tool_output, latency_ms, tokens_used, cost_usd,
                        cost_vnd, is_billable, execution_type, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    run_id,
                    step.step_number,
                    step.thought,
                    step.action_type,
                    step.tool_name,
                    tool_input_json,
                    tool_output_str,
                    step.latency_ms,
                    step.tokens_used,
                    step.cost_usd,
                    step.cost_vnd,
                    1 if step.is_billable else 0,
                    step.execution_type,
                    step.timestamp.isoformat() if isinstance(step.timestamp, datetime) else str(step.timestamp),
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save step {step.step_number} for run {run_id} to DB: {e}")

    def load_all_runs(self) -> List[AgentRunState]:
        """Loads all historical agent runs from SQLite database."""
        runs: List[AgentRunState] = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM agent_runs ORDER BY created_at DESC")
                rows = cursor.fetchall()
                for row in rows:
                    run_id = row["run_id"]
                    steps = self._load_steps_for_run(conn, run_id)
                    pending_approval = None
                    if row["pending_approval"]:
                        try:
                            pending_approval = ToolApprovalRequest.model_validate_json(row["pending_approval"])
                        except Exception:
                            pass

                    total_cost_usd = row["total_cost_usd"]
                    total_cost_vnd = row["total_cost_vnd"]

                    # Automatically recalculate cost if run has tokens but cost was 0.0
                    if row["total_tokens"] > 0 and (total_cost_usd is None or total_cost_usd <= 0.0):
                        try:
                            from app.core.pricing import pricing_registry
                            p_tok = max(1, int(row["total_tokens"] * 0.6))
                            c_tok = max(1, row["total_tokens"] - p_tok)
                            total_cost_usd = pricing_registry.calculate_cost(row["agent_name"] or "gemini-2.5-flash", p_tok, c_tok)
                            total_cost_vnd = round(total_cost_usd * settings.USD_TO_VND_RATE, 2)
                            for s in steps:
                                if s.tokens_used > 0 and (s.cost_usd is None or s.cost_usd <= 0.0):
                                    s_ptok = max(1, int(s.tokens_used * 0.6))
                                    s_ctok = max(1, s.tokens_used - s_ptok)
                                    s.cost_usd = pricing_registry.calculate_cost(s.tool_name or "gemini-2.5-flash", s_ptok, s_ctok)
                                    s.cost_vnd = round(s.cost_usd * settings.USD_TO_VND_RATE, 2)
                                    s.is_billable = True
                        except Exception as ex:
                            logger.warning(f"Could not auto-compute cost for run {run_id}: {ex}")

                    run = AgentRunState(
                        run_id=run_id,
                        agent_name=row["agent_name"],
                        prompt=row["prompt"],
                        status=AgentRunStatus(row["status"]),
                        current_step=row["current_step"],
                        max_steps=row["max_steps"],
                        total_tokens=row["total_tokens"],
                        total_cost_usd=total_cost_usd,
                        total_cost_vnd=total_cost_vnd,
                        is_simulation=bool(row["is_simulation"]),
                        pending_approval=pending_approval,
                        steps=steps,
                        final_output=row["final_output"],
                        error_message=row["error_message"],
                        langfuse_trace_id=row["langfuse_trace_id"],
                        langfuse_trace_url=row["langfuse_trace_url"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                    )
                    runs.append(run)
        except Exception as e:
            logger.error(f"Failed to load historical runs from DB: {e}")
        return runs

    def _load_steps_for_run(self, conn: sqlite3.Connection, run_id: str) -> List[AgentStepLog]:
        steps: List[AgentStepLog] = []
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agent_steps WHERE run_id = ? ORDER BY step_number ASC", (run_id,))
            for r in cursor.fetchall():
                tool_input = None
                if r["tool_input"]:
                    try:
                        tool_input = json.loads(r["tool_input"])
                    except Exception:
                        tool_input = {"raw": r["tool_input"]}

                tool_output = r["tool_output"]
                if tool_output and (tool_output.startswith("{") or tool_output.startswith("[")):
                    try:
                        tool_output = json.loads(tool_output)
                    except Exception:
                        pass

                steps.append(AgentStepLog(
                    step_number=r["step_number"],
                    thought=r["thought"],
                    action_type=r["action_type"] or "tool_call",
                    tool_name=r["tool_name"],
                    tool_input=tool_input,
                    tool_output=tool_output,
                    latency_ms=r["latency_ms"],
                    tokens_used=r["tokens_used"],
                    cost_usd=r["cost_usd"],
                    cost_vnd=r["cost_vnd"],
                    is_billable=bool(r["is_billable"]),
                    execution_type=r["execution_type"] or "llm_reasoning",
                    timestamp=datetime.fromisoformat(r["timestamp"]) if r["timestamp"] else get_utc_now(),
                ))
        except Exception as e:
            logger.error(f"Failed to load steps for run {run_id}: {e}")
        return steps


    def reset_all(self) -> int:
        """Deletes all runs and steps from SQLite and reclaims disk space."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT count(*) FROM agent_runs")
                count = cursor.fetchone()[0]
                cursor.execute("DELETE FROM agent_steps")
                cursor.execute("DELETE FROM agent_runs")
                conn.commit()
                cursor.execute("VACUUM")
                conn.commit()
            logger.info(f"Reset SQLite database: deleted {count} historical runs.")
            return count
        except Exception as e:
            logger.error(f"Failed to reset SQLite database: {e}")
            raise

    def get_storage_stats(self) -> dict:
        """Returns database disk usage, runs count, and steps count."""
        size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
        runs_count = 0
        steps_count = 0
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT count(*) FROM agent_runs")
                runs_count = cursor.fetchone()[0]
                cursor.execute("SELECT count(*) FROM agent_steps")
                steps_count = cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")

        size_formatted = f"{size_bytes / 1024:.1f} KB" if size_bytes < 1048576 else f"{size_bytes / 1048576:.2f} MB"
        return {
            "db_path": str(self.db_path),
            "size_bytes": size_bytes,
            "size_formatted": size_formatted,
            "runs_count": runs_count,
            "steps_count": steps_count,
        }

    def backup_to_file(self, target_path: Path) -> Path:
        """Creates an atomic SQLite backup file using sqlite3 backup API."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as source:
            with sqlite3.connect(str(target_path)) as dest:
                source.backup(dest)
        return target_path

    def restore_from_file(self, backup_path: Path) -> int:
        """Restores database from an external SQLite file."""
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        with sqlite3.connect(str(backup_path)) as source:
            with self._get_connection() as dest:
                source.backup(dest)
        self._init_db()
        return len(self.load_all_runs())


db = DatabaseManager()

