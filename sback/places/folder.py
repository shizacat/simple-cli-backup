"""Место хранения: копирование файла бэкапа в каталог."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field

from sback.lib.archive_name import is_archive_name
from sback.lib.config import Place
from sback.lib.exception import PlaceError
from sback.lib.place_base import PlaceBase


class FolderConfig(BaseModel):
    """Настройки места folder."""

    path: str = Field(description="Каталог для файлов бэкапа")


class Folder(PlaceBase[FolderConfig]):
    """Копирует файлы бэкапа в указанный каталог."""

    name: ClassVar[str] = "folder"
    description: ClassVar[str] = "Копирует файлы в указанную папку"
    config_model: ClassVar[type[FolderConfig]] = FolderConfig

    def __init__(self, config: Place):
        """Проверяет каталог назначения.

        Args:
            config: Конфигурация места. В config нужен path.

        Raises:
            PlaceError: настройки не соответствуют модели или path не каталог.
        """
        super().__init__(config)
        self._path: Path = self._checked_path()

    def _checked_path(self) -> Path:
        """Возвращает каталог из настройки path.

        Raises:
            PlaceError: path не существует или это не каталог.
        """
        path = Path(self._config_place.path)
        if not path.is_dir():
            raise PlaceError(
                f"путь {self._config_place.path} не существует или это не каталог"
            )
        return path

    # --- Override methods ---

    def copy(self, source: Path, file_name: str) -> None:
        """Копирует файл в каталог места.

        Args:
            source: Исходный файл.
            file_name: Имя файла в каталоге.

        Raises:
            PlaceError: файл не удалось скопировать.
        """
        try:
            shutil.copy2(source, self._path.joinpath(file_name))
        except OSError as exc:
            raise PlaceError(f"ошибка копирования: {exc}") from exc

    def list_files(self) -> list[str]:
        """Имена файлов бэкапа в каталоге назначения.

        Returns:
            Имена архивов в каталоге места.
        """
        names: list[str] = []
        for item in self._path.iterdir():
            if item.is_file() and is_archive_name(item.name):
                names.append(item.name)
        return names

    def delete_file(self, file_name: str) -> None:
        """Удаляет файл из каталога назначения.

        Args:
            file_name: Имя файла из list_files.

        Raises:
            PlaceError: имя файла недопустимо или файл не удалось удалить.
        """
        name = Path(file_name.replace("\\", "/")).name
        if name in {"", ".", ".."}:
            raise PlaceError(f"недопустимое имя файла: {file_name}")
        try:
            self._path.joinpath(name).unlink()
        except OSError as exc:
            raise PlaceError(f"ошибка удаления: {exc}") from exc
