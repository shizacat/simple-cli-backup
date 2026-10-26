import tarfile
from datetime import date
from pathlib import Path

import pytest

from sback.lib.backup import Backup
from sback.lib.config import Config
from sback.lib.exception import ConfigError


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
