import logging
from typing import Any, Dict, Optional
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


tracer = AgentTracer()
