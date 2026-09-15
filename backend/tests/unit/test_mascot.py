"""Mascot reference-photo loader: order, MIME types, fail-loud, fingerprint."""

from pathlib import Path

import pytest

from app.agents import mascot


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    mascot.load_mascot_refs.cache_clear()
    mascot.mascot_refs_version.cache_clear()


def _write(dir_: Path, name: str, data: bytes) -> None:
    (dir_ / name).write_bytes(data)


def test_loads_sorted_with_mime_by_suffix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mascot, "_DIR", tmp_path)
    _write(tmp_path, "02-face.png", b"png")
    _write(tmp_path, "01-front.jpg", b"jpg")
    _write(tmp_path, "notes.txt", b"ignored")

    refs = mascot.load_mascot_refs()

    assert [r.data for r in refs] == [b"jpg", b"png"]
    assert [r.mime_type for r in refs] == ["image/jpeg", "image/png"]


def test_missing_photos_fail_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mascot, "_DIR", tmp_path)
    with pytest.raises(mascot.MascotAssetsMissing):
        mascot.load_mascot_refs()


def test_version_is_stable_and_tracks_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mascot, "_DIR", tmp_path)
    _write(tmp_path, "01-front.jpg", b"a")
    v1 = mascot.mascot_refs_version()
    assert len(v1) == 12 and mascot.mascot_refs_version() == v1

    mascot.load_mascot_refs.cache_clear()
    mascot.mascot_refs_version.cache_clear()
    _write(tmp_path, "01-front.jpg", b"b")
    assert mascot.mascot_refs_version() != v1


def test_deployed_photos_present() -> None:
    """The committed assets must load — the pipeline fails loud without them."""
    refs = mascot.load_mascot_refs()
    assert len(refs) >= 1
    assert all(r.mime_type == "image/jpeg" for r in refs)
