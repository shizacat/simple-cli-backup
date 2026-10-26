from pathlib import Path

import pytest

from sback.lib.config import Config
from sback.lib.exception import ConfigError

VALID = """
name: daily
places:
  - name: local
    type: folder
    rotate:
      count: 4
    config:
      path: /tmp
  - name: cloud
    type: dropbox
    config:
      token: secret
slises:
  - name: main
    place:
      - local
      - cloud
    target:
      - name: files
        type: file
        config:
          path:
            - /var
    notify:
      - name: mail
        status: bad
notices:
  - name: mail
    type: email
    to:
      - a@example.com
"""


def test_from_yaml_reads_sections() -> None:
    config = Config.from_yaml(VALID)

    assert config.name == "daily"
    assert config.places[0].name == "local"
    assert config.places[0].type == "folder"
    assert config.places[0].config["path"] == "/tmp"
    assert config.places[0].rotate is not None
    assert config.places[0].rotate.count == 4
    assert config.places[1].config["token"] == "secret"
    assert config.slises[0].place == ["local", "cloud"]
    assert config.slises[0].target[0].config["path"] == ["/var"]
    assert config.slises[0].notify[0].status == "bad"
    assert config.notices[0].to == ["a@example.com"]


def test_from_yaml_fills_defaults() -> None:
    config = Config.from_yaml("""
places:
  - name: local
    type: folder
slises:
  - name: main
    place: [local]
    target:
      - name: files
        type: file
    notify:
      - name: mail
""")

    assert config.name is None
    assert config.places[0].rotate is None
    assert config.notices == []
    assert config.slises[0].notify[0].status is None


@pytest.mark.parametrize(
    "content",
    [
        "",
        "[]",
        "places: [",
        """
places:
  - name: local
slises:
  - name: main
    place: [local]
    target:
      - name: files
        type: file
""",
        """
places:
  - name: local
    type: folder
slises:
  - name: main
    place: []
    target:
      - name: files
        type: file
""",
        """
places:
  - name: local
    type: folder
slises:
  - name: main
    place: [local]
    target:
      - name: files
        type: file
    notify:
      - name: mail
        status: unknown
""",
    ],
)
def test_from_yaml_rejects_invalid(content: str) -> None:
    with pytest.raises(ConfigError):
        Config.from_yaml(content)


def test_from_file_accepts_str_and_path(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yml"
    config_file.write_text(VALID, encoding="utf-8")

    from_str = Config.from_file(str(config_file))
    from_path = Config.from_file(config_file)

    assert from_str == from_path
    assert from_path.places[0].name == "local"


def test_from_file_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        Config.from_file(tmp_path / "missing.yml")


def test_from_file_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        Config.from_file(tmp_path)
