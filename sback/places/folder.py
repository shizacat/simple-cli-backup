"""Место хранения: копирование файла бэкапа в каталог."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field

from sback.lib.config import Place
from sback.lib.exception import PlaceError
from sback.lib.place_base import PlaceBase

_FILE_NAME = re.compile(r".*_\d{4}\.\d{2}\.\d{2}(\.\d{4})?\.tar\Z")


class FolderRotate(BaseModel):
    """Сколько последних копий оставлять в каталоге."""

    count: int = Field(strict=True)


class FolderConfig(BaseModel):
    """Настройки места folder."""

    path: str = Field(description="Каталог для файлов бэкапа")
    rotate: FolderRotate | None = None


class Folder(PlaceBase[FolderConfig]):
    """Копирует файлы бэкапа в указанный каталог."""

    name: ClassVar[str] = "folder"
    description: ClassVar[str] = "Копирует файлы в указанную папку"
    config_model: ClassVar[type[FolderConfig]] = FolderConfig

    def __init__(self, config: Place):
        """Проверяет каталог назначения.

        Args:
            config: Конфигурация места. В config нужны path и, при ротации, rotate.

        Raises:
            PlaceError: настройки не соответствуют модели или path не каталог.
        """
        super().__init__(config)
        self._path = self._checked_path()
        self._rotate_count = (
            None
            if self._config_place.rotate is None
            else self._config_place.rotate.count
        )

    def process(self, result_path: str | Path) -> None:
        """Копирует файл бэкапа в каталог и удаляет лишние копии.

        Args:
            result_path: Путь к файлу результата бэкапа.

        Raises:
            PlaceError: файл не удалось скопировать или удалить при ротации.
        """
        source = Path(result_path)
        destination = self._path / self._unique_name(source.name)
        try:
            shutil.copy2(source, destination)
        except OSError as exc:
            raise PlaceError(f"ошибка копирования: {exc}") from exc
        self._rotate()

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

    def _unique_name(self, file_name: str) -> str:
        """Добавляет суффикс .NNNN, если файл с таким именем уже лежит в каталоге."""
        stem, dot, ext = file_name.rpartition(".")
        if not dot:
            return file_name
        indexed = re.compile(
            "^" + re.escape(stem) + r"\.(\d{4})\." + re.escape(ext) + "$"
        )
        plain = re.compile(
            "^" + re.escape(stem) + r"(?:\.(\d{4}))?\." + re.escape(ext) + "$"
        )
        highest: int | None = None
        for item in self._list_files():
            if plain.fullmatch(item) is None:
                continue
            found = indexed.fullmatch(item)
            number = int(found.group(1)) if found else 0
            highest = number if highest is None else max(highest, number)
        if highest is None:
            return file_name
        return f"{stem}.{highest + 1:04d}.{ext}"

    def _list_files(self) -> list[str]:
        """Имена файлов бэкапа в каталоге назначения."""
        names: list[str] = []
        for item in self._path.iterdir():
            if item.is_file() and _FILE_NAME.fullmatch(item.name):
                names.append(item.name)
        return names

    def _rotate(self) -> None:
        """Удаляет самые старые файлы, если их больше rotate.count.

        Raises:
            PlaceError: файл не удалось удалить.
        """
        if self._rotate_count is None:
            return
        names = self._list_files()
        extra = len(names) - self._rotate_count
        if extra <= 0:
            return
        for name in sorted(names, key=self._sort_key)[:extra]:
            self._delete(name)

    def _sort_key(self, name: str) -> str:
        """Ставит файл без числового суффикса перед копиями .0001 того же дня."""
        if len(name) >= 7 and name[-7] == ".":
            stem, _, ext = name.rpartition(".")
            return f"{stem}.0000.{ext}"
        return name

    def _delete(self, file_name: str) -> None:
        """Удаляет файл из каталога назначения.

        Raises:
            PlaceError: файл не удалось удалить.
        """
        try:
            (self._path / file_name).unlink()
        except OSError as exc:
            raise PlaceError(f"ошибка удаления: {exc}") from exc
