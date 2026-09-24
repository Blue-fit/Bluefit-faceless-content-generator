"""The weekly email carries the posting checklist — it lands when they act on it."""
from __future__ import annotations


from app.notifications import email


def test_checklist_covers_the_agreed_posting_rules() -> None:
    text = " ".join(email._CHECKLIST).lower()
    for must in ("reel", "trending audio", "20:00", "stories", "hashtags", "locatie"):
        assert must in text, f"checklist is missing: {must}"


def test_checklist_is_dutch_like_the_client() -> None:
    text = " ".join(email._CHECKLIST).lower()
    assert sum(w in text for w in ("de ", "je ", "niet", "voeg", "post")) >= 4


def test_checklist_items_are_valid_html_fragments() -> None:
    for item in email._CHECKLIST:
        assert item.count("<strong>") == item.count("</strong>"), item
        assert not item.startswith("<li"), "the <li> wrapper is added when rendering"
