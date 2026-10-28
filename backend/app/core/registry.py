import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.schemas.agent import AgentRunState, AgentRunStatus, ApprovalStatus, ApprovalDecision


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
    """Central registry and state manager for active and historical agent runs."""

    def __init__(self):
        self.runs: Dict[str, AgentRunHandle] = {}
        self._subscribers: List[asyncio.Queue] = []

    def register_run(self, state: AgentRunState) -> AgentRunHandle:
        handle = AgentRunHandle(state)
        self.runs[state.run_id] = handle
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

    def update_status(self, run_id: str, status: AgentRunStatus, error_message: Optional[str] = None):
        handle = self.runs.get(run_id)
        if not handle:
            return
        handle.state.status = status
        handle.state.updated_at = get_utc_now()
        if error_message:
            handle.state.error_message = error_message
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


registry = AgentRegistry()
