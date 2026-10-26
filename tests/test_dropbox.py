import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests
from dropbox.exceptions import ApiError
from dropbox.files import (
    CreateFolderError,
    FileMetadata,
    FolderMetadata,
    ListFolderError,
    LookupError,
    WriteConflictError,
    WriteError,
)

from sback.lib.config import Place
from sback.lib.exception import PlaceError
from sback.lib.place_base import PlaceBase
from sback.places.dropbox import Dropbox


def _place(token: str = "refresh-token", rotate: int | None = None) -> Dropbox:
    data: dict = {
        "name": "remote",
        "type": "dropbox",
        "config": {
            "token": token,
            "app_key": "app-key",
            "app_secret": "app-secret",
        },
    }
    if rotate is not None:
        data["rotate"] = {"count": rotate}
    return Dropbox(Place.model_validate(data))


def _file(name: str) -> FileMetadata:
    moment = datetime.datetime(2026, 10, 26, tzinfo=datetime.timezone.utc)
    return FileMetadata(
        name=name,
        id=f"id:{name}",
        client_modified=moment,
        server_modified=moment,
        rev="123456789",
        size=1,
    )


def _listing(*names: str, has_more: bool = False) -> MagicMock:
    result = MagicMock()
    result.entries = [_file(name) for name in names] + [
        FolderMetadata(name="nested", id="id:nested"),
        _file("notes.txt"),
    ]
    result.has_more = has_more
    result.cursor = "cursor"
    return result


def _client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    client = MagicMock()
    client.__enter__.return_value = client
    monkeypatch.setattr("sback.places.dropbox.DropboxClient", lambda **kwargs: client)
    return client


def test_factory_returns_dropbox() -> None:
    import sback.places  # регистрация подкласса

    config = Place.model_validate(
        {
            "name": "remote",
            "type": "dropbox",
            "config": {
                "token": "refresh-token",
                "app_key": "app-key",
                "app_secret": "app-secret",
            },
        }
    )
    assert isinstance(PlaceBase.factory(config), Dropbox)


def test_config_requires_app_key() -> None:
    with pytest.raises(PlaceError):
        Dropbox(
            Place.model_validate(
                {
                    "name": "remote",
                    "type": "dropbox",
                    "config": {"token": "refresh-token", "app_secret": "app-secret"},
                }
            )
        )


def test_copy_uploads_small_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "daily_2026.10.26.tar"
    source.write_bytes(b"backup")
    client = _client(monkeypatch)
    seen: dict = {}

    def factory(**kwargs: str) -> MagicMock:
        seen.update(kwargs)
        return client

    monkeypatch.setattr("sback.places.dropbox.DropboxClient", factory)

    _place().copy(source, "daily_2026.10.26.0000.tar")

    assert seen["oauth2_refresh_token"] == "refresh-token"
    assert seen["app_key"] == "app-key"
    assert seen["app_secret"] == "app-secret"
    client.files_create_folder_v2.assert_called_once_with("/remote")
    client.files_upload.assert_called_once_with(
        b"backup", "/remote/daily_2026.10.26.0000.tar"
    )


def test_copy_uses_upload_session_for_large_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "daily_2026.10.26.tar"
    source.write_bytes(b"0123456789")
    client = _client(monkeypatch)
    client.files_upload_session_start.return_value.session_id = "session-1"
    monkeypatch.setattr(Dropbox, "_CHUNK_SIZE", 4)

    _place().copy(source, "daily_2026.10.26.0000.tar")

    client.files_upload.assert_not_called()
    start = client.files_upload_session_start.call_args.args[0]
    append = client.files_upload_session_append_v2.call_args.args[0]
    finish = client.files_upload_session_finish.call_args.args[0]
    assert start == b"0123"
    assert append == b"4567"
    assert finish == b"89"


def test_copy_ignores_existing_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "daily_2026.10.26.tar"
    source.write_bytes(b"backup")
    client = _client(monkeypatch)
    client.files_create_folder_v2.side_effect = ApiError(
        "req",
        CreateFolderError.path(WriteError.conflict(WriteConflictError.folder)),
        None,
        None,
    )

    _place().copy(source, "daily_2026.10.26.0000.tar")

    client.files_upload.assert_called_once()


def test_copy_without_token_raises(tmp_path: Path) -> None:
    source = tmp_path / "daily_2026.10.26.tar"
    source.write_bytes(b"backup")
    with pytest.raises(PlaceError, match="token"):
        _place(token="").copy(source, "daily_2026.10.26.0000.tar")


def test_copy_wraps_request_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "daily_2026.10.26.tar"
    source.write_bytes(b"backup")
    client = _client(monkeypatch)
    client.files_upload.side_effect = requests.ConnectionError("offline")

    with pytest.raises(PlaceError, match="Dropbox"):
        _place().copy(source, "daily_2026.10.26.0000.tar")


def test_list_files_returns_archive_names(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    first = _listing("daily_2026.10.26.0000.tar", has_more=True)
    second = _listing("daily_2026.10.26.0001.tar.gz")
    client.files_list_folder.return_value = first
    client.files_list_folder_continue.return_value = second

    assert _place().list_files() == [
        "daily_2026.10.26.0000.tar",
        "daily_2026.10.26.0001.tar.gz",
    ]
    client.files_list_folder_continue.assert_called_once_with("cursor")


def test_list_files_missing_folder_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    client.files_list_folder.side_effect = ApiError(
        "req",
        ListFolderError.path(LookupError.not_found),
        None,
        None,
    )

    assert _place().list_files() == []


def test_delete_file_removes_archive(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)

    _place().delete_file(r"remote\daily_2026.10.26.0000.tar")

    client.files_delete_v2.assert_called_once_with("/remote/daily_2026.10.26.0000.tar")


def test_delete_file_rejects_parent_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)

    with pytest.raises(PlaceError, match="недопустимое имя"):
        _place().delete_file("..")

    client.files_delete_v2.assert_not_called()


def test_process_uploads_next_index_and_rotates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "daily_2026.10.27.tar"
    source.write_bytes(b"new")
    client = _client(monkeypatch)
    client.files_list_folder.side_effect = [
        _listing("daily_2026.10.26.0000.tar"),
        _listing("daily_2026.10.26.0000.tar", "daily_2026.10.27.0000.tar"),
    ]

    _place(rotate=1).process(source)

    uploaded = client.files_upload.call_args.args[1]
    assert uploaded == "/remote/daily_2026.10.27.0000.tar"
    client.files_delete_v2.assert_called_once_with("/remote/daily_2026.10.26.0000.tar")


def test_init_skips_prompt_when_token_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sback.places.dropbox.DropboxOAuth2FlowNoRedirect",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("oauth started")),
    )

    _place().init()


def test_init_prints_refresh_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    flow = MagicMock()
    flow.start.return_value = "https://dropbox.example/auth"
    flow.finish.return_value = SimpleNamespace(refresh_token="refresh-1")
    seen: dict = {}

    def factory(*args: str, **kwargs: str) -> MagicMock:
        seen["args"] = args
        seen["kwargs"] = kwargs
        return flow

    monkeypatch.setattr("sback.places.dropbox.DropboxOAuth2FlowNoRedirect", factory)
    monkeypatch.setattr("builtins.input", lambda prompt: "auth-code")

    _place(token="").init()

    assert seen["args"] == ("app-key", "app-secret")
    assert seen["kwargs"]["token_access_type"] == "offline"
    flow.finish.assert_called_once_with("auth-code")
    output = capsys.readouterr().out
    assert "https://dropbox.example/auth" in output
    assert "Token: refresh-1" in output
