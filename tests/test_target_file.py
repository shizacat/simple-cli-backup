import tarfile
from datetime import date
from pathlib import Path

import pytest

from sback.lib.config import Target
from sback.lib.exception import TargetError
from sback.lib.target_base import TargetBase
from sback.targets.file import File


def _target(*paths: str) -> File:
    config = Target.model_validate(
        {"name": "files", "type": "file", "config": {"path": list(paths)}}
    )
    return File(config)


def test_factory_returns_file(tmp_path: Path) -> None:
    import sback.targets  # регистрация подкласса

    config = Target.model_validate(
        {"name": "files", "type": "file", "config": {"path": [str(tmp_path)]}}
    )
    assert isinstance(TargetBase.factory(config), File)


def test_process_archives_existing_path(tmp_path: Path) -> None:
    source = tmp_path / "note.txt"
    source.write_text("backup", encoding="utf-8")
    result_dir = tmp_path / "result"
    result_dir.mkdir()

    archive_name = _target(str(source)).process(tmp_path, result_dir)

    today = date.today()
    assert archive_name == f"files_{today.year}.{today.month:02d}.{today.day:02d}.tar.gz"
    with tarfile.open(result_dir / archive_name, "r:gz") as tar:
        assert source.name in tar.getnames()[-1]


def test_process_skips_missing_path(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    result_dir.mkdir()

    archive_name = _target(str(tmp_path / "absent")).process(tmp_path, result_dir)

    with tarfile.open(result_dir / archive_name, "r:gz") as tar:
        assert tar.getnames() == []


def test_path_is_required() -> None:
    config = Target.model_validate({"name": "files", "type": "file", "config": {}})
    with pytest.raises(TargetError):
        File(config)
