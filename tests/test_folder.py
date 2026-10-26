from pathlib import Path

import pytest

from pydantic import ValidationError

from sback.lib.config import Place
from sback.lib.exception import PlaceError
from sback.lib.place_base import PlaceBase
from sback.places.folder import Folder


def _place(path: Path, rotate: int | None = None) -> Folder:
    data: dict = {
        "name": "local",
        "type": "folder",
        "config": {"path": str(path)},
    }
    if rotate is not None:
        data["rotate"] = {"count": rotate}
    return Folder(Place.model_validate(data))


def test_factory_returns_folder(tmp_path: Path) -> None:
    import sback.places  # регистрация подкласса

    config = Place.model_validate(
        {"name": "local", "type": "folder", "config": {"path": str(tmp_path)}}
    )
    assert isinstance(PlaceBase.factory(config), Folder)


def test_process_copies_archive(tmp_path: Path) -> None:
    source_dir = tmp_path / "src"
    destination = tmp_path / "dst"
    source_dir.mkdir()
    destination.mkdir()
    archive = source_dir / "daily_2026.10.26.tar"
    archive.write_bytes(b"backup")

    _place(destination).process(archive)

    assert (destination / "daily_2026.10.26.0000.tar").read_bytes() == b"backup"


def test_process_adds_index_when_name_exists(tmp_path: Path) -> None:
    source_dir = tmp_path / "src"
    destination = tmp_path / "dst"
    source_dir.mkdir()
    destination.mkdir()
    archive = source_dir / "daily_2026.10.26.tar"
    archive.write_bytes(b"new")
    (destination / "daily_2026.10.26.0000.tar").write_bytes(b"old")

    _place(destination).process(archive)

    assert (destination / "daily_2026.10.26.0000.tar").read_bytes() == b"old"
    assert (destination / "daily_2026.10.26.0001.tar").read_bytes() == b"new"


def test_process_rotates_oldest_files(tmp_path: Path) -> None:
    source_dir = tmp_path / "src"
    destination = tmp_path / "dst"
    source_dir.mkdir()
    destination.mkdir()
    for name in (
        "daily_2026.10.24.0000.tar",
        "daily_2026.10.25.0000.tar",
        "daily_2026.10.26.0000.tar",
    ):
        (destination / name).write_bytes(b"old")
    archive = source_dir / "daily_2026.10.27.tar"
    archive.write_bytes(b"new")

    _place(destination, rotate=2).process(archive)

    left = sorted(item.name for item in destination.iterdir())
    assert left == ["daily_2026.10.26.0000.tar", "daily_2026.10.27.0000.tar"]


def test_missing_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(PlaceError):
        _place(tmp_path / "absent")


def test_rotate_count_must_be_int() -> None:
    with pytest.raises(ValidationError):
        Place.model_validate(
            {
                "name": "local",
                "type": "folder",
                "config": {"path": "/tmp"},
                "rotate": {"count": "6"},
            }
        )
