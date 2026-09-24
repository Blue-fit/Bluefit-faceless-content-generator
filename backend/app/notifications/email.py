"""Resend email notifications.

Best-effort: if Resend isn't configured (no API key / from / recipient), or the
send fails, we log and return without raising — a notification must never fail
the weekly generation that triggered it.
"""

from __future__ import annotations

import asyncio

import resend
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

def _configured() -> bool:
    s = get_settings()
    return bool(s.resend_api_key.get_secret_value() and s.email_from and s.client_email)


async def send_weekly_digest(*, week_label: str, n_posts: int) -> None:
    """Email the client that this week's posts are ready, with a link to review."""
    s = get_settings()
    if not _configured():
        logger.warning("email.skipped", reason="resend_not_configured", week=week_label)
        return

    resend.api_key = s.resend_api_key.get_secret_value()
    url = s.frontend_url
    html = (
        f"<div style='font-family:Helvetica,Arial,sans-serif;color:#0f2438;"
        f"max-width:620px'>"
        f"<h2 style='color:#1E6EB4'>Je Blue Fit content staat klaar</h2>"
        f"<p>Er staan <strong>{n_posts} nieuwe posts</strong> klaar voor "
        f"<strong>{week_label}</strong>. Bekijk ze, pas aan wat je wilt, en download "
        f"de definitieve versies.</p>"
        f"<p><a href='{url}' style='background:#1E6EB4;color:#fff;padding:12px 20px;"
        f"border-radius:8px;text-decoration:none;display:inline-block'>"
        f"Bekijk je posts</a></p>"
        f"<p style='color:#5b7186;font-size:13px'>{url}</p>"
        f"</div>"
    )
    params: resend.Emails.SendParams = {
        "from": s.email_from,
        "to": [s.client_email],
        "subject": f"Je Blue Fit posts voor {week_label} staan klaar",
        "html": html,
    }
    try:
        await asyncio.to_thread(resend.Emails.send, params)
        logger.info("email.sent", to=s.client_email, week=week_label)
    except Exception:  # noqa: BLE001 - notifications are best-effort; never fail the cron
        logger.exception("email.failed", week=week_label)