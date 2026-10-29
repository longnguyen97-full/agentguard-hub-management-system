import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from app.schemas.agent import AgentRunState, AgentRunStatus, AgentStepLog, get_utc_now
from app.config import settings
from app.core.registry import registry
from app.core.db import db
from app.core.tracer import tracer

logger = logging.getLogger(__name__)


def _extract_attr_val(val_dict: Dict[str, Any]) -> Any:
    """Extracts raw value from OpenTelemetry AnyValue dictionary."""
    if not isinstance(val_dict, dict):
        return val_dict
    for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if key in val_dict:
            return val_dict[key]
    if "arrayValue" in val_dict:
        values = val_dict["arrayValue"].get("values", [])
        return [_extract_attr_val(v) for v in values]
    if "kvlistValue" in val_dict:
        values = val_dict["kvlistValue"].get("values", [])
        return {item.get("key"): _extract_attr_val(item.get("value", {})) for item in values}
    return str(val_dict)


def _attributes_to_dict(attributes_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Converts OTLP list of [{key: '...', value: {...}}] to a flat Python dict."""
    result = {}
    for attr in attributes_list:
        key = attr.get("key")
        val = attr.get("value", {})
        if key:
            result[key] = _extract_attr_val(val)
    return result


def process_otlp_trace_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parses OpenTelemetry standard JSON trace export payload (ExportTraceServiceRequest).
    Maps spans into AgentGuard sessions, steps, and telemetry metrics.
    """
    resource_spans = payload.get("resourceSpans", [])
    processed_spans = 0

    for res_span in resource_spans:
        resource = res_span.get("resource", {})
        res_attrs = _attributes_to_dict(resource.get("attributes", []))
        service_name = res_attrs.get("service.name") or res_attrs.get("agent.name") or "OTelAgent"

        for scope_span in res_span.get("scopeSpans", []):
            for span in scope_span.get("spans", []):
                trace_id = span.get("traceId", "")
                if not trace_id:
                    continue

                run_id = f"otel_{trace_id[:12]}"
                span_name = span.get("name", "span")
                span_attrs = _attributes_to_dict(span.get("attributes", []))

                # Extract latency
                start_nano = int(span.get("startTimeUnixNano", 0) or 0)
                end_nano = int(span.get("endTimeUnixNano", 0) or 0)
                latency_ms = round((end_nano - start_nano) / 1_000_000.0, 2) if end_nano > start_nano else 50.0

                # Extract tokens & costs
                input_tokens = int(span_attrs.get("gen_ai.usage.input_tokens", 0) or span_attrs.get("llm.token_count.prompt", 0) or 0)
                output_tokens = int(span_attrs.get("gen_ai.usage.output_tokens", 0) or span_attrs.get("llm.token_count.completion", 0) or 0)
                tokens_used = int(span_attrs.get("gen_ai.usage.total_tokens", 0) or span_attrs.get("llm.token_count.total", 0) or (input_tokens + output_tokens))

                cost_usd = float(span_attrs.get("gen_ai.usage.cost", 0.0) or span_attrs.get("llm.cost", 0.0) or 0.0)
                if cost_usd == 0.0 and tokens_used > 0:
                    cost_usd = round(tokens_used * 0.000002, 6)

                cost_vnd = round(cost_usd * settings.USD_TO_VND_RATE, 2)
                is_billable = tokens_used > 0 or cost_usd > 0.0 or "llm" in span_name.lower() or "chat" in span_name.lower()

                # Determine tool info
                tool_name = span_attrs.get("tool.name") or span_attrs.get("gen_ai.tool.name")
                if not tool_name and "tool" in span_name.lower():
                    tool_name = span_name

                thought = (
                    span_attrs.get("gen_ai.prompt")
                    or span_attrs.get("llm.prompt")
                    or span_attrs.get("thought")
                    or f"Executed span: {span_name}"
                )
                if isinstance(thought, list):
                    thought = " ".join(str(t) for t in thought)

                # Ensure run exists in registry
                handle = registry.get_handle(run_id)
                if not handle:
                    new_state = AgentRunState(
                        run_id=run_id,
                        agent_name=service_name,
                        prompt=str(thought)[:200],
                        status=AgentRunStatus.RUNNING,
                        max_steps=20,
                        is_simulation=False,
                        langfuse_trace_id=trace_id,
                        langfuse_trace_url=tracer.get_trace_url(trace_id) if tracer else None,
                        created_at=get_utc_now(),
                        updated_at=get_utc_now(),
                    )
                    registry.register_run(new_state)
                    handle = registry.get_handle(run_id)

                if handle:
                    step_number = len(handle.state.steps) + 1
                    step = AgentStepLog(
                        step_number=step_number,
                        thought=str(thought),
                        action_type="tool_call" if tool_name else "reasoning",
                        tool_name=tool_name,
                        tool_input=span_attrs.get("tool.parameters") or {},
                        tool_output=span_attrs.get("tool.output"),
                        latency_ms=latency_ms,
                        tokens_used=tokens_used,
                        cost_usd=cost_usd,
                        cost_vnd=cost_vnd,
                        is_billable=is_billable,
                        execution_type="llm_reasoning" if is_billable else "deterministic_tool",
                        timestamp=get_utc_now(),
                    )

                    handle.state.steps.append(step)
                    handle.state.current_step = step_number
                    handle.state.total_tokens += tokens_used
                    handle.state.total_cost_usd = round(handle.state.total_cost_usd + cost_usd, 6)
                    handle.state.total_cost_vnd = round(handle.state.total_cost_usd * settings.USD_TO_VND_RATE, 2)
                    handle.state.updated_at = get_utc_now()

                    db.save_run(handle.state)
                    db.save_step(run_id, step)

                    registry.broadcast_event({
                        "type": "step_completed",
                        "run_id": run_id,
                        "step": step.model_dump(mode="json"),
                        "total_tokens": handle.state.total_tokens,
                        "total_cost": handle.state.total_cost_usd,
                    })

                processed_spans += 1

    return {"partialSuccess": {}, "processed_spans": processed_spans}

