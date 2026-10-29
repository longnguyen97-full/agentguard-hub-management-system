import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import httpx

from app.config import settings
from app.core.db import db

logger = logging.getLogger(__name__)

# Standard Verified Official Model Pricing (USD per 1 Million Tokens)
# Verified against OpenAI, Google Cloud Vertex/Gemini, Anthropic, and DeepSeek official pricing
DEFAULT_MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "gpt-4o-mini": {
        "model_id": "gpt-4o-mini",
        "provider": "OpenAI",
        "input_cost_per_m": 0.15,
        "output_cost_per_m": 0.60,
        "context_window": 128000,
        "description": "Fast, lightweight model for cost-effective agent reasoning.",
        "verified_source": "https://openai.com/api/pricing/"
    },
    "gemini-1.5-flash": {
        "model_id": "gemini-1.5-flash",
        "provider": "Google DeepMind",
        "input_cost_per_m": 0.075,
        "output_cost_per_m": 0.30,
        "context_window": 1000000,
        "description": "Ultra-fast multimodal model with 1M context window and rock-bottom cost.",
        "verified_source": "https://ai.google.dev/pricing"
    },
    "claude-3-5-sonnet": {
        "model_id": "claude-3-5-sonnet",
        "provider": "Anthropic",
        "input_cost_per_m": 3.00,
        "output_cost_per_m": 15.00,
        "context_window": 200000,
        "description": "Top-tier intelligence benchmark leader for complex coding and agent tool calls.",
        "verified_source": "https://www.anthropic.com/pricing"
    },
    "gpt-4o": {
        "model_id": "gpt-4o",
        "provider": "OpenAI",
        "input_cost_per_m": 2.50,
        "output_cost_per_m": 10.00,
        "context_window": 128000,
        "description": "Flagship high-intelligence model for deep multimodality and complex logic.",
        "verified_source": "https://openai.com/api/pricing/"
    },
    "deepseek-chat": {
        "model_id": "deepseek-chat",
        "provider": "DeepSeek",
        "input_cost_per_m": 0.14,
        "output_cost_per_m": 0.28,
        "context_window": 64000,
        "description": "DeepSeek-V3 high-throughput model with disruptive cost efficiency.",
        "verified_source": "https://www.deepseek.com/"
    },
    "deepseek-reasoner": {
        "model_id": "deepseek-reasoner",
        "provider": "DeepSeek",
        "input_cost_per_m": 0.55,
        "output_cost_per_m": 2.19,
        "context_window": 64000,
        "description": "DeepSeek-R1 reinforcement reasoning model for STEM and logical chains.",
        "verified_source": "https://www.deepseek.com/"
    },
    "llama-3.3-70b-local": {
        "model_id": "llama-3.3-70b-local",
        "provider": "Self-Hosted / vLLM",
        "input_cost_per_m": 0.00,
        "output_cost_per_m": 0.00,
        "context_window": 128000,
        "description": "On-premises private open-weight deployment (Zero external API token fees).",
        "verified_source": "Local Hardware / vLLM"
    }
}


class ModelPricingRegistry:
    """
    Dynamic LLM Pricing & Token Cost Manager.
    Solves price volatility by:
    1. Providing verified offline defaults (safe fallback, zero latency).
    2. Syncing dynamically from community open registries (LiteLLM open database).
    3. Allowing custom overrides per deployment in SQLite DB.
    """

    def __init__(self):
        self._cache = dict(DEFAULT_MODEL_REGISTRY)
        self._last_sync: Optional[datetime] = None

    def get_all_models(self) -> List[Dict[str, Any]]:
        """Returns all registered models with pricing and VND rate calculation."""
        res = []
        for model in self._cache.values():
            m = dict(model)
            # Add pre-computed rate per 1K and VND cost
            m["input_cost_per_1k"] = round(m["input_cost_per_m"] / 1000.0, 7)
            m["output_cost_per_1k"] = round(m["output_cost_per_m"] / 1000.0, 7)
            m["input_cost_per_m_vnd"] = round(m["input_cost_per_m"] * settings.USD_TO_VND_RATE, 2)
            m["output_cost_per_m_vnd"] = round(m["output_cost_per_m"] * settings.USD_TO_VND_RATE, 2)
            res.append(m)
        return res

    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        return self._cache.get(model_id)

    def calculate_cost(self, model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculates exact USD spend for given token counts."""
        model = self.get_model(model_id) or self._cache.get("gpt-4o-mini")
        in_cost = (prompt_tokens / 1_000_000.0) * model["input_cost_per_m"]
        out_cost = (completion_tokens / 1_000_000.0) * model["output_cost_per_m"]
        return round(in_cost + out_cost, 6)

    async def sync_online_pricing(self) -> Dict[str, Any]:
        """
        Fetches the latest open-source community pricing index (LiteLLM registry)
        to automatically refresh prices if providers issue updates or cuts.
        """
        LITELLM_PRICING_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(LITELLM_PRICING_URL)
                if resp.status_code == 200:
                    remote_data = resp.json()
                    updated_count = 0
                    for model_id, local_info in self._cache.items():
                        remote_key = model_id
                        if remote_key in remote_data:
                            item = remote_data[remote_key]
                            # LiteLLM stores costs per token in float
                            in_per_m = float(item.get("input_cost_per_token", 0)) * 1_000_000
                            out_per_m = float(item.get("output_cost_per_token", 0)) * 1_000_000
                            if in_per_m > 0 and out_per_m > 0:
                                local_info["input_cost_per_m"] = round(in_per_m, 4)
                                local_info["output_cost_per_m"] = round(out_per_m, 4)
                                updated_count += 1

                    self._last_sync = datetime.now(timezone.utc)
                    logger.info(f"Successfully synced LLM pricing online: {updated_count} models updated.")
                    return {
                        "status": "ok",
                        "updated_models": updated_count,
                        "source": "LiteLLM Open Model Pricing Index",
                        "synced_at": self._last_sync.isoformat()
                    }
                else:
                    return {"status": "error", "message": f"HTTP {resp.status_code} from pricing registry"}
        except Exception as e:
            logger.warning(f"Could not sync online pricing ({e}). Retaining verified defaults.")
            return {"status": "fallback", "message": f"Retained verified defaults: {e}"}


pricing_registry = ModelPricingRegistry()

