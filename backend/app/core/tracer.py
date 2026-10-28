import logging
import httpx
from typing import Any, Dict, List, Optional
from langfuse import Langfuse
from app.config import settings

logger = logging.getLogger(__name__)


class AgentTracer:
    """Observability wrapper using Langfuse v5 SDK (OpenInference / OpenTelemetry standards)."""

    def __init__(self):
        self.enabled = False
        self.client: Optional[Langfuse] = None
        self.active_agent_spans: Dict[str, Any] = {}
        self._init_client()

    def _init_client(self):
        try:
            if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
                client = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_HOST,
                    timeout=1,
                )
                if client.auth_check():
                    self.client = client
                    self.enabled = True
                    logger.info(f"Langfuse tracer connected to: {settings.LANGFUSE_HOST}")
                else:
                    logger.warning("Langfuse auth check failed. Tracing disabled.")
                    self.enabled = False
            else:
                logger.warning("Langfuse credentials not set; tracer running in disabled mode.")
                self.enabled = False
        except Exception as e:
            logger.info(f"Langfuse offline or unreachable ({e}). Running in standalone mode.")
            self.enabled = False
            self.client = None

    def create_trace(
        self,
        run_id: str,
        name: str,
        user_id: Optional[str] = None,
        input_data: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Starts a top-level Agent Observation in Langfuse."""
        if not self.enabled or not self.client:
            return None
        try:
            agent_span = self.client.start_observation(
                name=name,
                as_type="agent",
                input=input_data,
                metadata=metadata or {},
            )
            self.active_agent_spans[run_id] = agent_span
            return agent_span.trace_id
        except Exception as e:
            logger.error(f"Failed to start agent observation in Langfuse: {e}")
            return None

    def log_generation(
        self,
        run_id: str,
        name: str,
        model: str,
        prompt: Any,
        completion: Any,
        usage: Optional[Dict[str, int]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Records an LLM reasoning generation step."""
        if not self.enabled or not self.client:
            return None
        parent = self.active_agent_spans.get(run_id, self.client)
        try:
            gen_span = parent.start_observation(
                name=name,
                as_type="generation",
                model=model,
                input=prompt,
                usage_details=usage,
                metadata=metadata or {},
            )
            gen_span.update(output=completion)
            gen_span.end()
            return gen_span
        except Exception as e:
            logger.error(f"Failed to log generation: {e}")
            return None

    def log_tool_span(
        self,
        run_id: str,
        tool_name: str,
        tool_input: Any,
        tool_output: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Records a tool execution step."""
        if not self.enabled or not self.client:
            return None
        parent = self.active_agent_spans.get(run_id, self.client)
        try:
            tool_span = parent.start_observation(
                name=f"tool:{tool_name}",
                as_type="tool",
                input=tool_input,
                metadata=metadata or {},
            )
            tool_span.update(output=tool_output)
            tool_span.end()
            return tool_span
        except Exception as e:
            logger.error(f"Failed to log tool span: {e}")
            return None

    def update_trace(self, run_id: str, output: Any = None, metadata: Optional[Dict[str, Any]] = None):
        """Finalizes the top-level Agent Observation."""
        if not self.enabled or not self.client:
            return
        agent_span = self.active_agent_spans.get(run_id)
        if not agent_span:
            return
        try:
            agent_span.update(output=output, metadata=metadata or {})
            agent_span.end()
            self.client.flush()
        except Exception as e:
            logger.error(f"Failed to finish trace in Langfuse: {e}")

    def score_trace(self, run_id: str, name: str, value: float, comment: Optional[str] = None):
        """Applies evaluation score (e.g. success, human review)."""
        if not self.enabled or not self.client:
            return
        agent_span = self.active_agent_spans.get(run_id)
        if not agent_span:
            return
        try:
            agent_span.score_trace(name=name, value=value, comment=comment)
        except Exception as e:
            logger.error(f"Failed to score trace: {e}")

    def get_trace_url(self, run_id: str) -> str:
        agent_span = self.active_agent_spans.get(run_id)
        trace_id = getattr(agent_span, "trace_id", None) if agent_span else None
        if trace_id and self.client:
            try:
                url = self.client.get_trace_url(trace_id=trace_id)
                if url:
                    return url
            except Exception:
                pass
        return f"{settings.LANGFUSE_HOST.rstrip('/')}/trace/{run_id}"

    def get_langfuse_telemetry(self) -> Dict[str, Any]:
        """Queries live telemetry stats from Langfuse Health and ClickHouse analytics."""
        connected = False
        version = "offline"
        try:
            with httpx.Client(timeout=1.5) as http:
                h_res = http.get(f"{settings.LANGFUSE_HOST}/api/public/health")
                if h_res.status_code == 200:
                    connected = True
                    version = h_res.json().get("version", "v4")
        except Exception:
            connected = False

        telemetry = {
            "connected": connected,
            "version": version,
            "host": settings.LANGFUSE_HOST,
            "total_traces": 0,
            "total_spans": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_cost_vnd": 0,
            "latest_traces": []
        }

        if connected:
            # Query ClickHouse for real aggregated telemetry
            try:
                with httpx.Client(timeout=2.0) as http:
                    ch_query = (
                        "SELECT count(DISTINCT trace_id) AS total_traces, "
                        "count() AS total_spans, "
                        "sum(arraySum(mapValues(usage_details))) AS total_tokens, "
                        "sum(calculated_total_cost) AS total_cost "
                        "FROM default.events_core FORMAT JSON"
                    )
                    res = http.get("http://127.0.0.1:8123/?query=" + ch_query, auth=("clickhouse", "clickhouse"))
                    if res.status_code == 200:
                        data = res.json().get("data", [{}])[0]
                        tokens = int(data.get("total_tokens", 0) or 0)
                        cost = float(data.get("total_cost", 0.0) or 0.0)
                        if cost == 0.0 and tokens > 0:
                            # Standard mini model pricing $0.30 per 1M tokens
                            cost = round(tokens / 1000.0 * 0.0003, 6)

                        telemetry["total_traces"] = int(data.get("total_traces", 0) or 0)
                        telemetry["total_spans"] = int(data.get("total_spans", 0) or 0)
                        telemetry["total_tokens"] = tokens
                        telemetry["total_cost_usd"] = cost
                        telemetry["total_cost_vnd"] = int(round(cost * settings.USD_TO_VND_RATE))

                    # Query latest traces for Live Mode feed
                    latest_query = (
                        "SELECT trace_id, name, min(start_time) AS start_time, "
                        "sum(arraySum(mapValues(usage_details))) AS tokens, count() AS spans "
                        "FROM default.events_core "
                        "GROUP BY trace_id, name "
                        "ORDER BY start_time DESC LIMIT 10 FORMAT JSON"
                    )
                    l_res = http.get("http://127.0.0.1:8123/?query=" + latest_query, auth=("clickhouse", "clickhouse"))
                    if l_res.status_code == 200:
                        raw_traces = l_res.json().get("data", [])
                        telemetry["latest_traces"] = [
                            {
                                "trace_id": t["trace_id"],
                                "name": t["name"],
                                "start_time": t["start_time"],
                                "tokens": int(t.get("tokens", 0) or 0),
                                "spans": int(t.get("spans", 0) or 0),
                                "trace_url": f"{settings.LANGFUSE_HOST}/project/agent-monitor/traces/{t['trace_id']}"
                            }
                            for t in raw_traces
                        ]
            except Exception as e:
                logger.debug(f"ClickHouse query error: {e}")

        return telemetry


tracer = AgentTracer()
