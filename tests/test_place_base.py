from pathlib import Path

import pytest
from pydantic import BaseModel

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


def test_factory_unknown_type() -> None:
    class _Nameless(PlaceBase):
        pass

    config = Place.model_validate({"name": "local", "type": "unknown", "config": {}})
    with pytest.raises(PlaceError, match="not found"):
        PlaceBase.factory(config)


def test_without_config_model_raises() -> None:
    config = Place.model_validate({"name": "local", "type": "folder", "config": {}})

    class _NoModel(PlaceBase):
        config_model = None

    class _NotAModel(PlaceBase):
        config_model = str

    with pytest.raises(PlaceError, match="модель настроек"):
        _NoModel(config)
    with pytest.raises(PlaceError, match="модель настроек"):
        _NotAModel(config)


def test_rotate_keeps_files_when_count_is_enough(tmp_path: Path) -> None:
    destination = tmp_path / "dst"
    destination.mkdir()
    stored = destination / "daily_2026.10.26.0000.tar"
    stored.write_bytes(b"old")

    _place(destination, rotate=2).rotate()

    assert stored.is_file()


def test_base_operations_are_not_implemented() -> None:
    class _Empty(BaseModel):
        pass

    class _Bare(PlaceBase[_Empty]):
        name = "bare-place"
        description = "bare"
        config_model = _Empty

    place = _Bare(
        Place.model_validate({"name": "local", "type": "bare-place", "config": {}})
    )
    with pytest.raises(NotImplementedError):
        place.copy(Path("archive.tar"), "archive.tar")
    with pytest.raises(NotImplementedError):
        place.list_files()
    with pytest.raises(NotImplementedError):
        place.delete_file("archive.tar")
