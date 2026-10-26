import tarfile
from datetime import date
from pathlib import Path

import pytest

from sback.lib.backup import Backup
from sback.lib.config import Config
from sback.lib.exception import ConfigError, TargetError
from sback.lib.place_base import PlaceBase
from sback.lib.target_base import TargetBase


def _config(source: Path, destination: Path) -> Config:
    return Config.from_yaml(f"""
places:
  - name: local
    type: folder
    config:
      path: "{destination}"
slises:
  - name: daily
    place: [local]
    target:
      - name: files
        type: file
        config:
          path:
            - "{source}"
""")


def test_process_stores_slise_archive(tmp_path: Path) -> None:
    source = tmp_path / "note.txt"
    source.write_text("backup", encoding="utf-8")
    destination = tmp_path / "backups"
    destination.mkdir()

    Backup(_config(source, destination)).process()

    today = date.today()
    stored = list(destination.iterdir())
    assert [item.name for item in stored] == [
        f"daily_{today.year}.{today.month:02d}.{today.day:02d}.0000.tar.gz"
    ]
    with tarfile.open(stored[0], "r:gz") as tar:
        assert tar.getnames() == ["note.txt"]


def test_init_initializes_places(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "note.txt"
    source.write_text("backup", encoding="utf-8")
    destination = tmp_path / "backups"
    destination.mkdir()
    started: list[str] = []
    monkeypatch.setattr(
        PlaceBase, "init", lambda self: started.append(self._config.name)
    )

    Backup(_config(source, destination)).init()

    assert started == ["local"]


def test_process_skips_place_when_target_has_no_files(tmp_path: Path) -> None:
    destination = tmp_path / "backups"
    destination.mkdir()

    Backup(_config(tmp_path / "absent.txt", destination)).process()

    assert list(destination.iterdir()) == []


def test_process_wraps_archive_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "note.txt"
    source.write_text("backup", encoding="utf-8")
    destination = tmp_path / "backups"
    destination.mkdir()

    class _MissingFile:
        def process(self, tmp_dir: Path) -> list[Path]:
            return [tmp_dir / "gone.txt"]

    monkeypatch.setattr(TargetBase, "factory", lambda config: _MissingFile())

    with pytest.raises(TargetError, match="сборки среза"):
        Backup(_config(source, destination)).process()

    assert list(destination.iterdir()) == []


def test_unknown_place_raises(tmp_path: Path) -> None:
    config = Config.from_yaml(f"""
places:
  - name: local
    type: folder
    config:
      path: "{tmp_path}"
slises:
  - name: daily
    place: [missing]
    target:
      - name: files
        type: file
        config:
          path:
            - "{tmp_path}"
""")
    with pytest.raises(ConfigError):
        Backup(config)
