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

# What the client should do when posting. It rides along with the weekly email
# because that is the moment they act on it. Dutch, because they are.
_CHECKLIST: tuple[str, ...] = (
    "Plaats <strong>alle drie als Reel</strong> — ook de foto's. Reels bereiken "
    "mensen die je nog niet volgen; een gewone feedpost vrijwel alleen je volgers.",
    "Voeg in Instagram <strong>trending audio</strong> toe. Kies iets dat nú opkomt, "
    "niet een nummer dat al overal voorbijkomt.",
    "Post <strong>'s avonds tussen 20:00 en 21:00</strong>.",
    "<strong>Spreid de drie posts over de week</strong> (bijvoorbeeld maandag, "
    "woensdag, vrijdag). Alle drie op één dag kost bereik.",
    "De <strong>eerste regel van de caption</strong> is de haak — Instagram kapt af "
    "na ongeveer 125 tekens. Wat daarvoor staat, bepaalt of iemand doorleest.",
    "Voeg een <strong>locatie</strong> toe: Nijmegen of Lent. Dat helpt lokaal bereik.",
    "Houd het op <strong>3–5 hashtags</strong> die echt bij het onderwerp passen.",
    "Zet er <strong>geen extra tekst overheen</strong> in Instagram — de tekst staat "
    "al in beeld. Dubbele tekst leest rommelig.",
    "<strong>Deel de post daarna in je Stories</strong> en reageer het eerste uur op "
    "reacties. Vroege interactie weegt zwaar.",
)


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
    steps = "".join(f"<li style='margin:0 0 10px'>{item}</li>" for item in _CHECKLIST)
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
        f"<h3 style='color:#1E6EB4;margin-top:28px'>Checklist voor je plaatst</h3>"
        f"<ol style='padding-left:20px;line-height:1.5'>{steps}</ol>"
        f"<p style='color:#5b7186;font-size:13px;margin-top:20px'>"
        f"Deze stappen bepalen samen een groot deel van je bereik — de content zelf "
        f"is maar de helft van het werk.</p>"
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