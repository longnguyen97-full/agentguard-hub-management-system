import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.pricing import pricing_registry, DEFAULT_MODEL_REGISTRY


def test_pricing_registry_calculations():
    # Test registered default models exist
    models = pricing_registry.get_all_models()
    model_ids = [m["model_id"] for m in models]
    assert "gpt-4o-mini" in model_ids
    assert "gemini-1.5-flash" in model_ids
    assert "claude-3-5-sonnet" in model_ids
    assert "deepseek-chat" in model_ids
    assert "llama-3.3-70b-local" in model_ids

    # Test exact cost calculation for gpt-4o-mini ($0.15/1M in, $0.60/1M out)
    # 1,000,000 prompt tokens = $0.15
    # 1,000,000 completion tokens = $0.60
    cost = pricing_registry.calculate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
    assert cost == 0.75

    # Test local self-hosted model has zero external cost
    cost_local = pricing_registry.calculate_cost("llama-3.3-70b-local", 5000, 2000)
    assert cost_local == 0.0


@pytest.mark.asyncio
async def test_pricing_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET pricing
        resp = await client.get("/api/agents/models/pricing")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "usd_to_vnd_rate" in data
        assert data["usd_to_vnd_rate"] == 25400

        # Verify a specific model payload structure
        mini = next(m for m in data["models"] if m["model_id"] == "gpt-4o-mini")
        assert mini["provider"] == "OpenAI"
        assert mini["input_cost_per_m"] == 0.15
        assert mini["output_cost_per_m"] == 0.60
        assert mini["input_cost_per_m_vnd"] > 0

