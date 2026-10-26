"""Место хранения: копирование файла бэкапа в Dropbox."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import requests
from dropbox import Dropbox as DropboxClient
from dropbox.exceptions import ApiError, DropboxException
from dropbox.files import CommitInfo, FileMetadata, UploadSessionCursor
from dropbox.oauth import (
    BadRequestException,
    BadStateException,
    CsrfException,
    DropboxOAuth2FlowNoRedirect,
    NotApprovedException,
    ProviderException,
)
from pydantic import BaseModel, Field

from sback.lib.archive_name import is_archive_name
from sback.lib.config import Place
from sback.lib.exception import PlaceError
from sback.lib.place_base import PlaceBase

_OAUTH_ERRORS = (
    BadRequestException,
    BadStateException,
    CsrfException,
    NotApprovedException,
    ProviderException,
)


class DropboxConfig(BaseModel):
    """Настройки места dropbox."""

    token: str = Field(
        default="",
        description="Refresh token. Пустая строка, пока init его не получил",
    )
    app_key: str = Field(min_length=1, description="App key приложения Dropbox")
    app_secret: str = Field(min_length=1, description="App secret приложения Dropbox")


class Dropbox(PlaceBase[DropboxConfig]):
    """Копирует файлы бэкапа в папку Dropbox с именем места."""

    name: ClassVar[str] = "dropbox"
    description: ClassVar[str] = "Копирует файлы в Dropbox"
    config_model: ClassVar[type[DropboxConfig]] = DropboxConfig
    _CHUNK_SIZE: ClassVar[int] = 40 * 1024 * 1024

    def _client(self) -> DropboxClient:
        """Открывает клиент Dropbox по refresh token.

        Returns:
            Клиент Dropbox. Его нужно закрывать через контекстный менеджер.

        Raises:
            PlaceError: token не задан.
        """
        token = self._config_place.token
        if token == "":
            raise PlaceError("не задан token")
        return DropboxClient(
            app_key=self._config_place.app_key,
            app_secret=self._config_place.app_secret,
            oauth2_refresh_token=token,
        )

    def _folder_path(self) -> str:
        """Путь папки места в Dropbox.

        Returns:
            Путь вида ``/{имя места}``.
        """
        return f"/{self._config.name}"

    def _ensure_folder(self, dbx: DropboxClient) -> None:
        """Создает папку места, если ее еще нет.

        Args:
            dbx: Открытый клиент Dropbox.

        Raises:
            ApiError: папку не удалось создать.
        """
        try:
            dbx.files_create_folder_v2(self._folder_path())
        except ApiError as exc:
            if not _is_conflict(exc):
                raise

    def _upload(self, dbx: DropboxClient, source: Path, dst_path: str) -> None:
        """Загружает файл целиком или частями не больше 40 МиБ.

        Args:
            dbx: Открытый клиент Dropbox.
            source: Локальный файл.
            dst_path: Путь файла в Dropbox.

        Raises:
            ApiError: Dropbox не принял файл.
            OSError: локальный файл не удалось прочитать.
        """
        file_size = source.stat().st_size
        with source.open("rb") as handle:
            if file_size <= self._CHUNK_SIZE:
                dbx.files_upload(handle.read(), dst_path)
                return

            session = dbx.files_upload_session_start(handle.read(self._CHUNK_SIZE))
            cursor = UploadSessionCursor(
                session_id=session.session_id,
                offset=handle.tell(),
            )
            commit = CommitInfo(path=dst_path)
            while handle.tell() < file_size:
                remaining = file_size - handle.tell()
                chunk = handle.read(self._CHUNK_SIZE)
                if remaining <= self._CHUNK_SIZE:
                    dbx.files_upload_session_finish(chunk, cursor, commit)
                    return
                dbx.files_upload_session_append_v2(chunk, cursor)
                cursor.offset = handle.tell()

    # --- Override methods ---

    def copy(self, source: Path, file_name: str) -> None:
        """Загружает файл в папку места в Dropbox.

        Args:
            source: Исходный файл.
            file_name: Имя файла в Dropbox.

        Raises:
            PlaceError: token не задан, имя недопустимо или загрузка не удалась.
        """
        destination = f"{self._folder_path()}/{_safe_name(file_name)}"
        try:
            with self._client() as dbx:
                self._ensure_folder(dbx)
                self._upload(dbx, source, destination)
        except (DropboxException, requests.RequestException, OSError) as exc:
            raise PlaceError(f"ошибка Dropbox: {exc}") from exc

    def list_files(self) -> list[str]:
        """Имена архивов в папке места.

        Returns:
            Имена архивов. Пустой список, если папки еще нет.

        Raises:
            PlaceError: token не задан или список файлов не удалось получить.
        """
        try:
            with self._client() as dbx:
                return self._archive_names(dbx)
        except ApiError as exc:
            if _is_not_found(exc):
                return []
            raise PlaceError(f"ошибка Dropbox: {exc}") from exc
        except (DropboxException, requests.RequestException) as exc:
            raise PlaceError(f"ошибка Dropbox: {exc}") from exc

    def _archive_names(self, dbx: DropboxClient) -> list[str]:
        """Собирает имена архивов из папки места.

        Args:
            dbx: Открытый клиент Dropbox.

        Returns:
            Имена файлов, которые подходят под шаблон архива.
        """
        names: list[str] = []
        result = dbx.files_list_folder(self._folder_path())
        while True:
            for item in result.entries:
                if isinstance(item, FileMetadata) and is_archive_name(item.name):
                    names.append(item.name)
            if not result.has_more:
                return names
            result = dbx.files_list_folder_continue(result.cursor)

    def delete_file(self, file_name: str) -> None:
        """Удаляет файл из папки места.

        Args:
            file_name: Имя файла из list_files.

        Raises:
            PlaceError: имя недопустимо, token не задан или файл не удалось удалить.
        """
        destination = f"{self._folder_path()}/{_safe_name(file_name)}"
        try:
            with self._client() as dbx:
                dbx.files_delete_v2(destination)
        except (DropboxException, requests.RequestException) as exc:
            raise PlaceError(f"ошибка Dropbox: {exc}") from exc

    def init(self) -> None:
        """Печатает refresh token, если поле token еще пустое.

        Raises:
            PlaceError: авторизация Dropbox не завершилась.
        """
        if self._config_place.token:
            return

        print(f"Initializing for: {self._config.name}")
        print("Perform the following steps:")
        try:
            token = self._authorize()
        except PlaceError:
            raise
        except (DropboxException, requests.RequestException, *_OAUTH_ERRORS) as exc:
            raise PlaceError(f"ошибка Dropbox: {exc}") from exc

        print(f"Token: {token}")
        print('4. This token you need enter into field "token" in config file')

    def _authorize(self) -> str:
        """Запрашивает у пользователя код и обменивает его на refresh token.

        Returns:
            Refresh token.

        Raises:
            PlaceError: Dropbox не вернул refresh token.
            DropboxException: запрос авторизации не удался.
            requests.RequestException: нет связи с Dropbox.
        """
        flow = DropboxOAuth2FlowNoRedirect(
            self._config_place.app_key,
            self._config_place.app_secret,
            token_access_type="offline",
        )
        authorize_url = flow.start()
        print(f"1. Go to: {authorize_url}")
        print('2. Click "Allow" (you might have to log in first)')
        print("3. Copy the authorization code.")
        code = input("Enter the authorization code here: ").strip()
        result = flow.finish(code)
        if not result.refresh_token:
            raise PlaceError("Dropbox не вернул refresh token")
        return result.refresh_token


def _safe_name(file_name: str) -> str:
    """Оставляет только имя файла без пути.

    Args:
        file_name: Имя файла из места хранения.

    Returns:
        Последний компонент пути.

    Raises:
        PlaceError: имя пустое или указывает на родительский каталог.
    """
    name = Path(file_name.replace("\\", "/")).name
    if name in {"", ".", ".."}:
        raise PlaceError(f"недопустимое имя файла: {file_name}")
    return name


def _is_not_found(exc: ApiError) -> bool:
    """Проверяет, что ошибка Dropbox означает отсутствие пути.

    Args:
        exc: Ошибка ответа API.

    Returns:
        ``True``, если путь не найден.
    """
    return _path_matches(exc, "is_not_found")


def _is_conflict(exc: ApiError) -> bool:
    """Проверяет, что папка уже существует.

    Args:
        exc: Ошибка ответа API.

    Returns:
        ``True``, если путь уже занят.
    """
    return _path_matches(exc, "is_conflict")


def _path_matches(exc: ApiError, check: str) -> bool:
    """Смотрит признак ошибки пути.

    Args:
        exc: Ошибка ответа API.
        check: Имя метода признака, например ``is_not_found``.

    Returns:
        ``True``, если у ошибки пути этот признак включен.
    """
    error = exc.error
    is_path = getattr(error, "is_path", None)
    if not callable(is_path) or not is_path():
        return False
    predicate = getattr(error.get_path(), check, None)
    return callable(predicate) and bool(predicate())
