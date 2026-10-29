import asyncio
import logging
from typing import Any, Dict, Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class AlertNotifier:
    """Dispatches webhook alerts for critical safety events (Kill Switch, Approvals, Loops)."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.ALERT_WEBHOOK_URL

    async def send_alert_async(self, title: str, message: str, level: str = "WARNING", metadata: Optional[Dict[str, Any]] = None):
        """Asynchronously dispatches an alert payload to the configured webhook."""
        url = self.webhook_url or settings.ALERT_WEBHOOK_URL
        if not url:
            logger.debug(f"[Alert Skipped - No Webhook Configured] {level}: {title} - {message}")
            return

        payload = self._format_payload(url, title, message, level, metadata or {})

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code >= 400:
                    logger.warning(f"Webhook dispatch failed with status {resp.status_code}: {resp.text}")
                    return False
                logger.info(f"Alert webhook sent successfully: {title}")
                return True
        except Exception as e:
            logger.warning(f"Could not deliver alert webhook: {e}")
            return False

    def trigger(self, title: str, message: str, level: str = "WARNING", metadata: Optional[Dict[str, Any]] = None):
        """Fire-and-forget alert trigger safe to call from synchronous code or event loops."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.send_alert_async(title, message, level, metadata))
        except RuntimeError:
            # No running event loop
            pass

    def _format_payload(self, url: str, title: str, message: str, level: str, metadata: Dict[str, Any]) -> dict:
        color_map = {
            "INFO": 0x3B82F6,      # Blue
            "WARNING": 0xF59E0B,   # Amber
            "CRITICAL": 0xEF4444,  # Red
            "SUCCESS": 0x10B981,   # Green
        }
        color = color_map.get(level.upper(), 0xF59E0B)

        # 1. Discord Webhook
        if "discord.com" in url:
            fields = [{"name": k, "value": str(v), "inline": True} for k, v in metadata.items()]
            return {
                "username": "AgentGuard Security",
                "embeds": [{
                    "title": f"🚨 {title}" if level in ["WARNING", "CRITICAL"] else f"ℹ️ {title}",
                    "description": message,
                    "color": color,
                    "fields": fields,
                    "footer": {"text": "AgentGuard Autonomous Safety Layer"}
                }]
            }

        # 2. Slack Webhook
        elif "slack.com" in url:
            meta_str = " | ".join([f"*{k}*: {v}" for k, v in metadata.items()])
            return {
                "text": f"*{title}*\n{message}\n{meta_str}"
            }

        # 3. Generic JSON Webhook
        return {
            "source": "AgentGuard",
            "level": level,
            "title": title,
            "message": message,
            "metadata": metadata
        }


alert_notifier = AlertNotifier()
notifier = alert_notifier

