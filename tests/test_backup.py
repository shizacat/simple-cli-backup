import tarfile
from datetime import date
from pathlib import Path

import pytest

from sback.lib.backup import Backup
from sback.lib.config import Config
from sback.lib.exception import ConfigError, NotifyError, PlaceError, TargetError
from sback.notices.email import Email
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


def _notice_config(source: Path, destination: Path, *, notify: str) -> Config:
    return Config.from_yaml(f"""
places:
  - name: local
    type: folder
    config:
      path: "{destination}"
notices:
  - name: always
    type: email
    config:
      server: localhost
      to: [a@example.com]
      from: backup@example.com
  - name: on-good
    type: email
    config:
      server: localhost
      to: [b@example.com]
      from: backup@example.com
  - name: on-bad
    type: email
    config:
      server: localhost
      to: [c@example.com]
      from: backup@example.com
slises:
  - name: daily
    place: [local]
    notify:
{notify}
    target:
      - name: files
        type: file
        config:
          path:
            - "{source}"
""")


def _capture_mail(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    sent: list[tuple[str, str]] = []

    def capture(self: Email, body: str) -> None:
        sent.append((self._config.name, body))

    monkeypatch.setattr("sback.notices.email.Email.send", capture)
    return sent


def test_process_sends_matching_notices(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "note.txt"
    source.write_text("backup", encoding="utf-8")
    destination = tmp_path / "backups"
    destination.mkdir()
    sent = _capture_mail(monkeypatch)

    Backup(
        _notice_config(
            source,
            destination,
            notify="      - name: always\n      - name: on-good\n        status: good\n      - name: on-bad\n        status: bad",
        )
    ).process()

    assert [name for name, _ in sent] == ["always", "on-good"]
    assert "daily - Success" in sent[0][1]
    assert "files - Success" in sent[0][1]
    assert "local - Success" in sent[0][1]


def test_process_reports_target_error_and_notifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "note.txt"
    source.write_text("backup", encoding="utf-8")
    destination = tmp_path / "backups"
    destination.mkdir()
    sent = _capture_mail(monkeypatch)

    class _MissingFile:
        def process(self, tmp_dir: Path) -> list[Path]:
            return [tmp_dir / "gone.txt"]

    backup = Backup(
        _notice_config(
            source,
            destination,
            notify="      - name: on-good\n        status: good\n      - name: on-bad\n        status: bad",
        )
    )
    monkeypatch.setattr(TargetBase, "factory", lambda config: _MissingFile())

    with pytest.raises(TargetError, match="сборки среза"):
        backup.process()

    assert [name for name, _ in sent] == ["on-bad"]
    assert "files - Error" in sent[0][1]
    assert "daily - Error" in sent[0][1]
    assert list(destination.iterdir()) == []


def test_process_reports_place_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "note.txt"
    source.write_text("backup", encoding="utf-8")
    destination = tmp_path / "backups"
    destination.mkdir()
    sent = _capture_mail(monkeypatch)

    def fail_place(self: object, result_path: Path) -> None:
        raise PlaceError("disk full")

    monkeypatch.setattr("sback.places.folder.Folder.process", fail_place)
    with pytest.raises(PlaceError, match="disk full"):
        Backup(
            _notice_config(
                source,
                destination,
                notify="      - name: on-bad\n        status: bad",
            )
        ).process()

    assert [name for name, _ in sent] == ["on-bad"]
    assert "files - Success" in sent[0][1]
    assert "local - Error. disk full" in sent[0][1]


def test_process_raises_notify_error_after_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "note.txt"
    source.write_text("backup", encoding="utf-8")
    destination = tmp_path / "backups"
    destination.mkdir()

    def fail_send(self: object, body: str) -> None:
        raise NotifyError("smtp down")

    monkeypatch.setattr("sback.notices.email.Email.send", fail_send)
    with pytest.raises(NotifyError, match="smtp down"):
        Backup(
            _notice_config(source, destination, notify="      - name: always")
        ).process()

    assert list(destination.iterdir())


def test_process_keeps_backup_error_when_notice_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "note.txt"
    source.write_text("backup", encoding="utf-8")
    destination = tmp_path / "backups"
    destination.mkdir()

    class _MissingFile:
        def process(self, tmp_dir: Path) -> list[Path]:
            return [tmp_dir / "gone.txt"]

    def fail_send(self: object, body: str) -> None:
        raise NotifyError("smtp down")

    backup = Backup(_notice_config(source, destination, notify="      - name: always"))
    monkeypatch.setattr(TargetBase, "factory", lambda config: _MissingFile())
    monkeypatch.setattr("sback.notices.email.Email.send", fail_send)

    with pytest.raises(TargetError, match="сборки среза"):
        backup.process()


def test_unknown_notice_name_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="канал"):
        Backup(_notice_config(tmp_path, tmp_path, notify="      - name: missing"))


def test_archive_open_error_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "note.txt"
    source.write_text("backup", encoding="utf-8")
    destination = tmp_path / "backups"
    destination.mkdir()
    sent = _capture_mail(monkeypatch)

    def fail_open(*args: object, **kwargs: object) -> None:
        raise OSError("no space")

    backup = Backup(
        _notice_config(
            source, destination, notify="      - name: on-bad\n        status: bad"
        )
    )
    monkeypatch.setattr("sback.lib.backup.tarfile.open", fail_open)

    with pytest.raises(TargetError, match="no space"):
        backup.process()

    assert "files - Error" in sent[0][1]
