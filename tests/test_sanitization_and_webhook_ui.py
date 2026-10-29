import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.sanitizer import sanitize_text, sanitize_payload
from app.main import app


def test_vietnamese_text_sanitizer():
    """Verifies that mojibake and encoding issues are repaired automatically."""
    # 1. Latin-1 / UTF-8 Mojibake
    mojibake = "MÃ¨o bÃ©o tiáº¿ng Viá»‡t"
    fixed = sanitize_text(mojibake)
    assert "Mèo" in fixed
    assert "tiếng Việt" in fixed

    # 2. Escaped unicode
    escaped = "M\\u1ef9 ph\\u1ea9m tr\\u1ecb m\\u1ee5n"
    fixed_escaped = sanitize_text(escaped)
    assert "Mỹ phẩm trị mụn" in fixed_escaped

    # 3. Payload dict recursion
    data = {
        "title": "BÃ¡o cÃ¡o",
        "nested": ["Tiáº¿ng Viá»‡t", 123]
    }
    cleaned = sanitize_payload(data)
    assert "Báo cáo" in cleaned["title"]
    assert "Tiếng Việt" in cleaned["nested"][0]


@pytest.mark.asyncio
async def test_alerts_config_and_test_endpoint():
    """Verifies GET/POST /api/agents/alerts/config and /alerts/test."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Initial config
        get_res = await ac.get("/api/agents/alerts/config")
        assert get_res.status_code == 200
        data = get_res.json()
        assert "supported_channels" in data

        # Update webhook URL
        post_res = await ac.post("/api/agents/alerts/config", json={
            "webhook_url": "https://discord.com/api/webhooks/test/123"
        })
        assert post_res.status_code == 200
        assert post_res.json()["configured"] is True
        assert settings.ALERT_WEBHOOK_URL == "https://discord.com/api/webhooks/test/123"

        # Reset
        await ac.post("/api/agents/alerts/config", json={"webhook_url": ""})
        assert settings.ALERT_WEBHOOK_URL is None


@pytest.mark.asyncio
async def test_export_aliases():
    """Verifies both /export/all and /runs/export/all work without 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r1 = await ac.get("/api/agents/export/all")
        assert r1.status_code == 200
        assert "text/csv" in r1.headers["content-type"]

        r2 = await ac.get("/api/agents/runs/export/all")
        assert r2.status_code == 200
        assert "text/csv" in r2.headers["content-type"]

