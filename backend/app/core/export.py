import csv
import io
import json
from typing import Any, Dict, List, Optional

from app.core.registry import registry
from app.schemas.agent import AgentRunState


def export_run_to_json(run_id: str) -> Optional[Dict[str, Any]]:
    """Exports comprehensive structured audit telemetry for an agent run."""
    run = registry.get_run(run_id)
    if not run:
        return None

    # Calculate analytics
    billable_steps = [s for s in run.steps if s.is_billable]
    deterministic_steps = [s for s in run.steps if not s.is_billable]

    total_billable_cost = sum(s.cost_usd for s in billable_steps)
    total_billable_tokens = sum(s.tokens_used for s in billable_steps)

    export_payload = {
        "export_metadata": {
            "exporter": "AgentGuard Audit Exporter",
            "version": "1.0",
            "run_id": run.run_id,
        },
        "session_summary": {
            "agent_name": run.agent_name,
            "status": run.status.value,
            "is_simulation": run.is_simulation,
            "prompt": run.prompt,
            "current_step": run.current_step,
            "max_steps": run.max_steps,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            "final_output": run.final_output,
            "error_message": run.error_message,
            "langfuse_trace_id": run.langfuse_trace_id,
            "langfuse_trace_url": run.langfuse_trace_url,
        },
        "cost_and_token_audit": {
            "total_tokens": run.total_tokens,
            "total_cost_usd": run.total_cost_usd,
            "total_cost_vnd": run.total_cost_vnd,
            "billable_steps_count": len(billable_steps),
            "deterministic_steps_count": len(deterministic_steps),
            "billable_cost_usd": round(total_billable_cost, 6),
            "billable_tokens": total_billable_tokens,
        },
        "pending_approval": run.pending_approval.model_dump(mode="json") if run.pending_approval else None,
        "steps": [step.model_dump(mode="json") for step in run.steps],
    }
    return export_payload


def export_run_to_csv(run_id: str) -> Optional[str]:
    """Exports steps of a specific run to CSV format for Excel/auditing."""
    run = registry.get_run(run_id)
    if not run:
        return None

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "run_id",
        "step_number",
        "action_type",
        "execution_type",
        "is_billable",
        "tokens_used",
        "cost_usd",
        "cost_vnd",
        "latency_ms",
        "timestamp",
        "tool_name",
        "thought",
        "tool_output",
    ])

    for step in run.steps:
        thought_clean = (step.thought or "").replace("\n", " ").strip()
        tool_output_str = str(step.tool_output) if step.tool_output is not None else ""
        if len(tool_output_str) > 500:
            tool_output_str = tool_output_str[:500] + "..."

        writer.writerow([
            run.run_id,
            step.step_number,
            step.action_type,
            step.execution_type,
            "Yes" if step.is_billable else "No (Deterministic/0đ)",
            step.tokens_used,
            f"{step.cost_usd:.6f}",
            f"{step.cost_vnd:.2f}",
            step.latency_ms or 0.0,
            step.timestamp.isoformat() if step.timestamp else "",
            step.tool_name or "",
            thought_clean,
            tool_output_str.replace("\n", " "),
        ])

    return output.getvalue()


def export_all_runs_to_csv() -> str:
    """Exports high-level summary of all runs in registry to CSV."""
    runs = registry.list_runs()
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "run_id",
        "agent_name",
        "status",
        "is_simulation",
        "current_step",
        "max_steps",
        "total_tokens",
        "total_cost_usd",
        "total_cost_vnd",
        "created_at",
        "updated_at",
        "error_message",
        "prompt",
    ])

    for run in runs:
        prompt_clean = (run.prompt or "").replace("\n", " ").strip()
        writer.writerow([
            run.run_id,
            run.agent_name,
            run.status.value,
            "Simulation" if run.is_simulation else "Live",
            run.current_step,
            run.max_steps,
            run.total_tokens,
            f"{run.total_cost_usd:.6f}",
            f"{run.total_cost_vnd:.2f}",
            run.created_at.isoformat() if run.created_at else "",
            run.updated_at.isoformat() if run.updated_at else "",
            run.error_message or "",
            prompt_clean[:200],
        ])

    return output.getvalue()

