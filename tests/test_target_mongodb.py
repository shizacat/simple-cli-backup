import subprocess
from pathlib import Path

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from sback.lib.config import Target
from sback.lib.exception import TargetError
from sback.lib.target_base import TargetBase
from sback.targets.mongodb import Mongodb


def _target(**config: object) -> Mongodb:
    config.setdefault("uri", "mongodb://localhost")
    return Mongodb(
        Target.model_validate({"name": "mongo", "type": "mongodb", "config": config})
    )


def test_factory_returns_mongodb() -> None:
    import sback.targets  # регистрация подкласса

    config = Target.model_validate(
        {
            "name": "mongo",
            "type": "mongodb",
            "config": {"uri": "mongodb://localhost", "database": "app"},
        }
    )
    assert isinstance(TargetBase.factory(config), Mongodb)


def test_database_defaults_to_all() -> None:
    assert _target()._config_target.database == "*"


def test_uri_is_required() -> None:
    with pytest.raises(TargetError):
        Mongodb(
            Target.model_validate({"name": "mongo", "type": "mongodb", "config": {}})
        )


def test_matching_databases_supports_star() -> None:
    names = ["zeta", "app", "app_logs", "other"]
    assert _target()._matching_databases(names) == [
        "app",
        "app_logs",
        "other",
        "zeta",
    ]
    assert _target(database="app_*")._matching_databases(names) == ["app_logs"]
    assert _target(database="app")._matching_databases(names) == ["app"]
    assert _target(database="missing*")._matching_databases(names) == []


def test_process_dumps_each_matching_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []

    class FakeClient:
        def list_database_names(self) -> list[str]:
            return ["zeta", "app", "app_logs"]

        def close(self) -> None:
            return None

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        assert kwargs.get("shell") in {None, False}
        commands.append(command)
        archive = next(
            part.split("=", 1)[1] for part in command if part.startswith("--archive=")
        )
        Path(archive).write_bytes(b"dump")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(
        "sback.targets.mongodb.MongoClient", lambda *args, **kwargs: FakeClient()
    )
    monkeypatch.setattr("sback.targets.mongodb.subprocess.run", fake_run)

    paths = list(
        _target(uri="mongodb://backup:secret@db.internal:27018").process(tmp_path)
    )

    assert [path.name for path in paths] == [
        "app.archive.gz",
        "app_logs.archive.gz",
        "zeta.archive.gz",
    ]
    assert all(path.read_bytes() == b"dump" for path in paths)
    assert commands[0][:3] == [
        "mongodump",
        "--uri",
        "mongodb://backup:secret@db.internal:27018",
    ]
    assert "--db" in commands[0]
    assert commands[0][commands[0].index("--db") + 1] == "app"


def test_process_uses_uri(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    class FakeClient:
        def list_database_names(self) -> list[str]:
            return ["app"]

        def close(self) -> None:
            return None

    def fake_client(*args: object, **kwargs: object) -> FakeClient:
        seen["args"] = args
        seen["kwargs"] = kwargs
        return FakeClient()

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        seen["command"] = command
        archive = next(
            part.split("=", 1)[1] for part in command if part.startswith("--archive=")
        )
        Path(archive).write_bytes(b"dump")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("sback.targets.mongodb.MongoClient", fake_client)
    monkeypatch.setattr("sback.targets.mongodb.subprocess.run", fake_run)

    list(_target(uri="mongodb://localhost/admin", database="app").process(tmp_path))

    assert seen["args"] == ("mongodb://localhost/admin",)
    command = seen["command"]
    assert isinstance(command, list)
    assert command[:3] == ["mongodump", "--uri", "mongodb://localhost/admin"]


def test_process_raises_when_nothing_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeClient:
        def list_database_names(self) -> list[str]:
            return ["other"]

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "sback.targets.mongodb.MongoClient", lambda *args, **kwargs: FakeClient()
    )

    with pytest.raises(TargetError, match="app_\\*"):
        list(_target(database="app_*").process(tmp_path))


def test_process_wraps_connection_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeClient:
        def list_database_names(self) -> list[str]:
            raise ServerSelectionTimeoutError("offline")

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "sback.targets.mongodb.MongoClient", lambda *args, **kwargs: FakeClient()
    )

    with pytest.raises(TargetError, match="MongoDB"):
        list(_target().process(tmp_path))


def test_process_wraps_mongodump_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeClient:
        def list_database_names(self) -> list[str]:
            return ["app"]

        def close(self) -> None:
            return None

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, "", "auth failed")

    monkeypatch.setattr(
        "sback.targets.mongodb.MongoClient", lambda *args, **kwargs: FakeClient()
    )
    monkeypatch.setattr("sback.targets.mongodb.subprocess.run", fake_run)

    with pytest.raises(TargetError, match="auth failed"):
        list(_target(database="app").process(tmp_path))


def test_process_reports_missing_mongodump(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeClient:
        def list_database_names(self) -> list[str]:
            return ["app"]

        def close(self) -> None:
            return None

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(
        "sback.targets.mongodb.MongoClient", lambda *args, **kwargs: FakeClient()
    )
    monkeypatch.setattr("sback.targets.mongodb.subprocess.run", fake_run)

    with pytest.raises(TargetError, match="mongodump"):
        list(_target(database="app").process(tmp_path))
