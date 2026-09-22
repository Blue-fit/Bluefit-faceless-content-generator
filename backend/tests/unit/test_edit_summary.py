"""The reply must say what changed and what didn't — never leave the client guessing."""

from __future__ import annotations

from app.tools.edit_post import summarise_edit

HOOK_OLD = "Natuurlijk bewegen: het ritme van het bos.\nLees de caption"
HOOK_NEW = "Waarom de trap gratis krachttraining is?\nLees de caption"


def _s(**kw: object) -> str:
    base: dict[str, object] = dict(
        post_type="image",
        media_rerendered=False,
        hook_before=HOOK_OLD,
        hook_after=HOOK_OLD,
        caption_changed=False,
        caption_followed_asset=False,
        version_number=3,
    )
    base.update(kw)
    return summarise_edit(**base)  # type: ignore[arg-type]


def test_text_only_edit_says_the_picture_is_untouched() -> None:
    """The July complaint: they could not tell whether the photo was replaced."""
    reply = _s(hook_after=HOOK_NEW, caption_changed=True, caption_followed_asset=True)
    assert 'set the on-screen text to "Waarom de trap gratis krachttraining is?"' in reply
    assert "rewrote the caption to match" in reply
    assert "photo itself is untouched" in reply
    assert "version 3" in reply
    assert "\n" not in reply  # the CTA line never leaks into the sentence


def test_regenerated_video_is_named_as_a_new_video() -> None:
    reply = _s(post_type="video", media_rerendered=True, hook_after=HOOK_NEW)
    assert "made a new video" in reply
    assert 'set the on-screen text to "Waarom de trap gratis krachttraining is?"' in reply
    assert "caption is unchanged" in reply


def test_caption_only_edit_reassures_about_the_media() -> None:
    reply = _s(caption_changed=True)
    assert "rewrote the caption" in reply and "to match" not in reply
    assert "photo and its on-screen text are unchanged" in reply


def test_new_media_with_the_same_hook_says_so() -> None:
    reply = _s(media_rerendered=True)
    assert "made a new photo" in reply
    assert "on-screen text is unchanged" in reply
    assert "caption is unchanged" in reply


def test_a_no_op_asks_instead_of_claiming_success() -> None:
    """Claiming 'Done' when nothing changed is what made the system untrustworthy."""
    reply = _s()
    assert "could not change anything" in reply
    assert "Done" not in reply
    assert "the caption, the text in the image, or the photo itself" in reply


def test_both_changes_are_reported_in_one_sentence() -> None:
    reply = _s(media_rerendered=True, hook_after=HOOK_NEW, caption_changed=True)
    assert reply.count(" and ") >= 1
    for fragment in ("made a new photo", "set the on-screen text", "rewrote the caption"):
        assert fragment in reply
