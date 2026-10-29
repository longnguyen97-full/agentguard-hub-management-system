import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.schemas.agent import AgentRunState, AgentRunStatus, ApprovalStatus, ApprovalDecision, AgentStepLog
from app.core.db import db
from app.core.alerts import alert_notifier


def get_utc_now():
    return datetime.now(timezone.utc)

logger = logging.getLogger(__name__)


class AgentRunHandle:
    def __init__(self, state: AgentRunState):
        self.state = state
        self.kill_requested: bool = False
        self.approval_event: asyncio.Event = asyncio.Event()
        self.approval_decision: Optional[ApprovalDecision] = None
        self.task: Optional[asyncio.Task] = None


class AgentRegistry:
    """Central registry and state manager with SQLite persistence and Webhook alerts."""

    def __init__(self):
        self.runs: Dict[str, AgentRunHandle] = {}
        self._subscribers: List[asyncio.Queue] = []
        self._load_persisted_runs()

    def _load_persisted_runs(self):
        """Loads historical runs from SQLite database on startup."""
        try:
            persisted_runs = db.load_all_runs()
            for run_state in persisted_runs:
                self.runs[run_state.run_id] = AgentRunHandle(run_state)
            if persisted_runs:
                logger.info(f"Loaded {len(persisted_runs)} historical runs from SQLite persistence.")
        except Exception as e:
            logger.error(f"Failed to load historical runs from DB: {e}")

    def register_run(self, state: AgentRunState) -> AgentRunHandle:
        handle = AgentRunHandle(state)
        self.runs[state.run_id] = handle
        # Persist to SQLite
        db.save_run(state)
        self.broadcast_event({"type": "run_registered", "run": state.model_dump(mode="json")})
        return handle

    def get_handle(self, run_id: str) -> Optional[AgentRunHandle]:
        return self.runs.get(run_id)

    def get_run(self, run_id: str) -> Optional[AgentRunState]:
        handle = self.runs.get(run_id)
        return handle.state if handle else None

    def list_runs(self) -> List[AgentRunState]:
        # Return sorted by created_at desc
        return sorted([h.state for h in self.runs.values()], key=lambda s: s.created_at, reverse=True)

    def record_step(self, run_id: str, step: AgentStepLog):
        """Records a step log, updates running totals, and persists to SQLite."""
        handle = self.runs.get(run_id)
        if not handle:
            return

        handle.state.steps.append(step)
        handle.state.current_step = step.step_number
        handle.state.total_tokens += step.tokens_used
        handle.state.total_cost_usd = round(handle.state.total_cost_usd + step.cost_usd, 6)
        from app.config import settings
        handle.state.total_cost_vnd = round(handle.state.total_cost_usd * settings.USD_TO_VND_RATE, 2)
        handle.state.updated_at = get_utc_now()

        # Persist to SQLite
        db.save_step(run_id, step)
        db.save_run(handle.state)

        self.broadcast_event({
            "type": "step_completed",
            "run_id": run_id,
            "step": step.model_dump(mode="json"),
            "total_tokens": handle.state.total_tokens,
            "total_cost": handle.state.total_cost_usd
        })

    def update_status(self, run_id: str, status: AgentRunStatus, error_message: Optional[str] = None):
        handle = self.runs.get(run_id)
        if not handle:
            return
        handle.state.status = status
        handle.state.updated_at = get_utc_now()
        if error_message:
            handle.state.error_message = error_message

        # Persist to SQLite
        db.save_run(handle.state)

        # Trigger Webhook Alert if approval needed or failed
        if status == AgentRunStatus.WAITING_APPROVAL:
            tool_name = handle.state.pending_approval.tool_name if handle.state.pending_approval else "Unknown Tool"
            alert_notifier.trigger(
                title=f"Approval Required: {handle.state.agent_name}",
                message=f"Agent execution paused for sensitive action `{tool_name}`. Awaiting supervisor decision.",
                level="WARNING",
                metadata={"run_id": run_id, "tool": tool_name, "prompt": handle.state.prompt[:100]}
            )
        elif status == AgentRunStatus.FAILED:
            alert_notifier.trigger(
                title=f"Agent Guardrail Triggered: {handle.state.agent_name}",
                message=f"Run failed or halted by safety guardrail: {error_message or 'Unknown reason'}",
                level="CRITICAL",
                metadata={"run_id": run_id, "error": error_message or "N/A"}
            )

        self.broadcast_event({"type": "status_changed", "run_id": run_id, "status": status.value, "error": error_message})

    def request_kill(self, run_id: str) -> bool:
        """Trigger the emergency kill switch for a specific agent execution."""
        handle = self.runs.get(run_id)
        if not handle:
            return False

        handle.kill_requested = True
        handle.state.status = AgentRunStatus.KILLED
        handle.state.error_message = "Agent execution terminated by operator kill switch."
        handle.state.updated_at = get_utc_now()

        # Persist to SQLite
        db.save_run(handle.state)

        # Dispatch Alert
        alert_notifier.trigger(
            title=f"Emergency Kill Switch Activated",
            message=f"Operator terminated run `{run_id}` ({handle.state.agent_name}).",
            level="CRITICAL",
            metadata={"run_id": run_id, "agent_name": handle.state.agent_name}
        )

        # If waiting on approval, wake it up immediately so it exits cleanly
        if not handle.approval_event.is_set():
            handle.approval_decision = ApprovalDecision(approved=False, user="admin", comment="Killed by admin")
            handle.approval_event.set()

        if handle.task and not handle.task.done():
            handle.task.cancel()

        logger.warning(f"Kill switch activated for run {run_id}")
        self.broadcast_event({"type": "run_killed", "run_id": run_id})
        return True

    def resolve_approval(self, run_id: str, decision: ApprovalDecision) -> bool:
        """Resolve a pending Human-in-the-Loop authorization request."""
        handle = self.runs.get(run_id)
        if not handle or not handle.state.pending_approval:
            return False

        handle.approval_decision = decision
        handle.state.pending_approval.status = ApprovalStatus.APPROVED if decision.approved else ApprovalStatus.REJECTED
        handle.state.pending_approval.decided_by = decision.user
        handle.state.pending_approval.decided_at = get_utc_now()
        handle.state.updated_at = get_utc_now()

        # Persist to SQLite
        db.save_run(handle.state)

        # Dispatch Alert
        action_verb = "APPROVED" if decision.approved else "REJECTED"
        alert_notifier.trigger(
            title=f"Human-in-the-Loop Decision: {action_verb}",
            message=f"Operator `{decision.user}` has {action_verb} action for run `{run_id}`. Comment: {decision.comment or 'None'}",
            level="SUCCESS" if decision.approved else "WARNING",
            metadata={"run_id": run_id, "decision": action_verb, "user": decision.user}
        )

        # Unblock the agent loop
        handle.approval_event.set()
        logger.info(f"Approval for run {run_id} resolved: {decision.approved} by {decision.user}")
        self.broadcast_event({
            "type": "approval_resolved",
            "run_id": run_id,
            "approved": decision.approved,
            "user": decision.user
        })
        return True

    def subscribe(self) -> asyncio.Queue:
        """Subscribes to SSE event updates."""
        queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def broadcast_event(self, data: dict):
        for q in list(self._subscribers):
            try:
                q.put_nowait(data)
            except Exception:
                pass


    def reload_from_db(self):
        """Clears memory state and reloads freshly from SQLite database."""
        self.runs.clear()
        self._load_persisted_runs()
        self.broadcast_event({
            "type": "runs_reloaded",
            "count": len(self.runs)
        })

    def clear_all(self):
        """Wipes in-memory runs dictionary and broadcasts event."""
        self.runs.clear()
        self.broadcast_event({
            "type": "runs_cleared"
        })


registry = AgentRegistry()
