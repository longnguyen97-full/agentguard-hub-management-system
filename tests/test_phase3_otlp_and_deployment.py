import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.registry import registry
from app.core.otlp import process_otlp_trace_payload
from app.main import app


SAMPLE_OTLP_PAYLOAD = {
    "resourceSpans": [
        {
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "CrewAI-FinancialAnalyst"}},
                    {"key": "environment", "value": {"stringValue": "production"}}
                ]
            },
            "scopeSpans": [
                {
                    "scope": {"name": "crewai.telemetry", "version": "0.1.0"},
                    "spans": [
                        {
                            "traceId": "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d",
                            "spanId": "0123456789abcdef",
                            "name": "chat_completion",
                            "kind": 1,
                            "startTimeUnixNano": "1700000000000000000",
                            "endTimeUnixNano": "1700000001500000000",
                            "attributes": [
                                {"key": "gen_ai.prompt", "value": {"stringValue": "Analyze Q3 market revenue for tech sector"}},
                                {"key": "gen_ai.usage.input_tokens", "value": {"intValue": 450}},
                                {"key": "gen_ai.usage.output_tokens", "value": {"intValue": 180}},
                                {"key": "gen_ai.usage.total_tokens", "value": {"intValue": 630}},
                                {"key": "gen_ai.usage.cost", "value": {"doubleValue": 0.00126}}
                            ],
                            "status": {"code": 1}
                        },
                        {
                            "traceId": "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d",
                            "spanId": "fedcba9876543210",
                            "name": "tool_execute_calculator",
                            "kind": 1,
                            "startTimeUnixNano": "1700000001600000000",
                            "endTimeUnixNano": "1700000001650000000",
                            "attributes": [
                                {"key": "tool.name", "value": {"stringValue": "revenue_multiplier"}},
                                {"key": "gen_ai.usage.total_tokens", "value": {"intValue": 0}},
                                {"key": "gen_ai.usage.cost", "value": {"doubleValue": 0.0}}
                            ],
                            "status": {"code": 1}
                        }
                    ]
                }
            ]
        }
    ]
}


def test_process_otlp_trace_payload():
    """Verifies parsing of standard OpenTelemetry spans into sessions and steps."""
    result = process_otlp_trace_payload(SAMPLE_OTLP_PAYLOAD)
    assert result.get("processed_spans") == 2
    assert "partialSuccess" in result

    run_id = "otel_9a8b7c6d5e4f"
    run = registry.get_run(run_id)
    assert run is not None
    assert run.agent_name == "CrewAI-FinancialAnalyst"
    assert len(run.steps) >= 2

    # Step 1: LLM Reasoning (Billable)
    step1 = run.steps[0]
    assert step1.tokens_used == 630
    assert step1.cost_usd == 0.00126
    assert step1.is_billable is True
    assert step1.latency_ms == 1500.0

    # Step 2: Tool execution (Deterministic / Free)
    step2 = run.steps[1]
    assert step2.tool_name == "revenue_multiplier"
    assert step2.tokens_used == 0
    assert step2.cost_usd == 0.0
    assert step2.is_billable is False


@pytest.mark.asyncio
async def test_otlp_http_endpoints_and_auth():
    """Verifies POST /v1/traces and /api/otlp/v1/traces endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Open Mode
        settings.API_KEY = None
        resp_v1 = await ac.post("/v1/traces", json=SAMPLE_OTLP_PAYLOAD)
        assert resp_v1.status_code == 200
        data_v1 = resp_v1.json()
        assert "partialSuccess" in data_v1

        resp_alias = await ac.post("/api/otlp/v1/traces", json=SAMPLE_OTLP_PAYLOAD)
        assert resp_alias.status_code == 200

        # 2. Enforced API Key Mode
        settings.API_KEY = "otlp_secret_key_888"
        try:
            # Unauthorized without key
            resp_unauth = await ac.post("/v1/traces", json=SAMPLE_OTLP_PAYLOAD)
            assert resp_unauth.status_code == 401

            # Authorized with key
            resp_auth = await ac.post(
                "/v1/traces",
                json=SAMPLE_OTLP_PAYLOAD,
                headers={"X-API-Key": "otlp_secret_key_888"}
            )
            assert resp_auth.status_code == 200
        finally:
            settings.API_KEY = None

