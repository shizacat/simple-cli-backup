import subprocess
from pathlib import Path

import pytest
from mysql.connector import Error

from sback.lib.config import Target
from sback.lib.exception import TargetError
from sback.lib.target_base import TargetBase
from sback.targets.mysql import Mysql


def _target(**config: object) -> Mysql:
    config.setdefault("host", "db.internal")
    config.setdefault("user", "backup")
    return Mysql(
        Target.model_validate({"name": "db", "type": "mysql", "config": config})
    )


class _Cursor:
    def __init__(self, databases: list[str], rows: list[tuple[object, ...]]) -> None:
        self.sql = ""
        self.databases = databases
        self.rows = rows

    def execute(self, sql: str, params: object = None) -> None:
        self.sql = sql

    def fetchall(self) -> list[tuple[object, ...]]:
        if self.sql == "SHOW DATABASES":
            return [(name,) for name in self.databases]
        if self.sql.startswith("SHOW FULL TABLES"):
            return [("items", "BASE TABLE"), ("v_items", "VIEW")]
        if self.sql.startswith("SELECT"):
            return list(self.rows)
        return []

    def fetchone(self) -> tuple[object, ...] | None:
        if self.sql.startswith("SHOW CREATE TABLE"):
            return ("items", "CREATE TABLE `items` (`id` int)")
        return None

    def close(self) -> None:
        return None


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self.cursor_obj = cursor
        self.closed = False

    def cursor(self) -> _Cursor:
        return self.cursor_obj

    def close(self) -> None:
        self.closed = True


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    databases: list[str],
    rows: list[tuple[object, ...]],
) -> list[dict[str, object]]:
    seen: list[dict[str, object]] = []
    cursor = _Cursor(databases, rows)

    def connect(**kwargs: object) -> _Connection:
        seen.append(kwargs)
        return _Connection(cursor)

    monkeypatch.setattr("sback.targets.mysql.mysql.connector.connect", connect)
    return seen


def test_factory_returns_mysql() -> None:
    import sback.targets  # регистрация подкласса

    config = Target.model_validate(
        {
            "name": "db",
            "type": "mysql",
            "config": {"host": "localhost", "user": "backup"},
        }
    )
    assert isinstance(TargetBase.factory(config), Mysql)


def test_database_defaults_to_all_user_databases() -> None:
    assert _target()._config_target.database == "*"


def test_process_dumps_matching_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _patch(
        monkeypatch,
        ["zeta", "app", "app_logs", "information_schema", "mysql"],
        [(1, None, "o'brien")],
    )

    paths = list(_target(password="secret", port=3307).process(tmp_path))

    assert [path.name for path in paths] == [
        "app.sql",
        "app_logs.sql",
        "zeta.sql",
    ]
    script = paths[0].read_text(encoding="utf-8")
    assert "CREATE TABLE `items` (`id` int);" in script
    assert "INSERT INTO `items` VALUES (1, NULL, 'o\\'brien');" in script
    assert "v_items" not in script
    assert seen[0]["password"] == "secret"
    assert seen[0]["port"] == 3307
    assert seen[1]["database"] == "app"


def test_process_can_dump_named_system_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch(monkeypatch, ["mysql", "app"], [])

    paths = list(_target(database="mysql").process(tmp_path))

    assert [path.name for path in paths] == ["mysql.sql"]


def test_process_raises_when_nothing_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch(monkeypatch, ["other"], [])

    with pytest.raises(TargetError, match="app_\\*"):
        list(_target(database="app_*").process(tmp_path))


def test_process_wraps_connection_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def connect(**kwargs: object) -> _Connection:
        raise Error("offline")

    monkeypatch.setattr("sback.targets.mysql.mysql.connector.connect", connect)

    with pytest.raises(TargetError, match="MySQL"):
        list(_target().process(tmp_path))


def test_process_uses_mysqldump_utility(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch(monkeypatch, ["app", "other"], [])
    commands: list[list[str]] = []

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        result_file = next(
            part.split("=", 1)[1]
            for part in command
            if part.startswith("--result-file=")
        )
        Path(result_file).write_text("-- mysqldump\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("sback.targets.mysql.subprocess.run", fake_run)

    paths = list(
        _target(database="app", password="secret", mysqldump=True).process(tmp_path)
    )

    assert paths[0].read_text(encoding="utf-8") == "-- mysqldump\n"
    assert commands[0][0] == "mysqldump"
    assert "--single-transaction" in commands[0]
    assert "--routines" in commands[0]
    assert "--password=secret" in commands[0]
    assert commands[0][-1] == "app"


def test_process_wraps_mysqldump_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch(monkeypatch, ["app"], [])

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, "", "access denied")

    monkeypatch.setattr("sback.targets.mysql.subprocess.run", fake_run)

    with pytest.raises(TargetError, match="access denied"):
        list(_target(database="app", mysqldump=True).process(tmp_path))
