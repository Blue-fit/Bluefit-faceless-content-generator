"""Pure helpers for in-place (base-image) text-resize edits."""

from app.tools.edit_post import _ext_ctype


def test_ext_ctype_jpg() -> None:
    assert _ext_ctype("https://pub.r2.dev/weeks/w/p-base.jpg") == (".jpg", "image/jpeg")
    assert _ext_ctype("https://pub.r2.dev/x/p-base.jpeg") == (".jpg", "image/jpeg")


def test_ext_ctype_png() -> None:
    assert _ext_ctype("https://pub.r2.dev/weeks/w/p-base.png") == (".png", "image/png")


def test_ext_ctype_video_default() -> None:
    assert _ext_ctype("https://pub.r2.dev/weeks/w/p-base.mp4") == (".mp4", "video/mp4")
