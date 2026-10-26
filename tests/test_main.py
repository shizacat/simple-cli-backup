from pathlib import Path

import pytest

from sback.lib.backup import Backup
from sback.main import main


def _write_config(path: Path, source: Path, destination: Path) -> None:
    path.write_text(
        f"""
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
""",
        encoding="utf-8",
    )


def _paths(tmp_path: Path) -> Path:
    source = tmp_path / "note.txt"
    source.write_text("backup", encoding="utf-8")
    destination = tmp_path / "backups"
    destination.mkdir()
    config_file = tmp_path / "backup.yml"
    _write_config(config_file, source, destination)
    return config_file


def test_short_flag_checks_config_without_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config_file = _paths(tmp_path)

    def fail_process(self: Backup) -> None:
        raise AssertionError("backup started")

    monkeypatch.setattr(Backup, "process", fail_process)

    assert main(["-t", str(config_file)]) == 0
    assert capsys.readouterr().out.strip() == "Success"


def test_config_test_checks_without_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config_file = _paths(tmp_path)

    def fail_process(self: Backup) -> None:
        raise AssertionError("backup started")

    monkeypatch.setattr(Backup, "process", fail_process)

    assert main(["--config-test", str(config_file)]) == 0
    assert capsys.readouterr().out.strip() == "Success"


def test_config_runs_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = _paths(tmp_path)
    started: list[bool] = []
    monkeypatch.setattr(Backup, "process", lambda self: started.append(True))

    assert main(["--config", str(config_file)]) == 0
    assert started == [True]


def test_missing_config_file(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-t", "missing.yml"]) == 1
    assert capsys.readouterr().out.strip() == "The file of settings not found"


def test_config_and_test_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit):
        main(["--config", "a.yml", "-t", "b.yml"])


def test_plugin_info_lists_registered_plugins(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--plugin-info"]) == 0
    assert capsys.readouterr().out == (
        "Target plugins:\n"
        "    file - Работает с файлами и каталогами\n"
        "\n"
        "Place plugins:\n"
        "    folder - Копирует файлы в указанную папку\n"
        "    dropbox - Копирует файлы в Dropbox\n"
    )
