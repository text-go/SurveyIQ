from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.services.ai_chat import ask_survey_agent


async def build_report_summary(db: Any, survey_id: int, user_query: str, provider: str = "mistral", mode: str = "deep_research") -> str:
    """Generate a sharper, leadership-ready survey report summary."""
    return await ask_survey_agent(
        db=db,
        survey_id=survey_id,
        user_query=user_query,
        provider=provider,
        mode=mode,
    )


async def send_report_to_webhook(report_body: str, webhook_url: str | None = None, recipient: str | None = None) -> dict[str, Any]:
    """Dispatch the generated report to an optional webhook endpoint.

    This acts as a lightweight MCP-style report delivery tool: if a webhook URL is configured,
    the report is forwarded as JSON. If no webhook is configured, it safely returns a disabled state.
    """
    target = (webhook_url or settings.REPORT_WEBHOOK_URL or "").strip()
    if not target:
        return {
            "status": "skipped",
            "message": "No report webhook configured. Configure REPORT_WEBHOOK_URL in the backend settings.",
        }

    payload = {
        "recipient": recipient or "survey-team",
        "report": report_body,
        "source": "SurveyIQ automated report dispatch",
    }

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(target, json=payload)
        response.raise_for_status()

    return {
        "status": "sent",
        "message": f"Report dispatched to {target}",
        "recipient": recipient or "survey-team",
    }
