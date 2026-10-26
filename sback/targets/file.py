"""Цель бэкапа: файлы и каталоги."""

from __future__ import annotations

import tarfile
from datetime import date
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field

from sback.lib.config import Target
from sback.lib.exception import TargetError
from sback.lib.target_base import TargetBase


class FileConfig(BaseModel):
    """Настройки цели file."""

    path: list[str] = Field(min_length=1, description="Файлы и каталоги для архива")


class File(TargetBase[FileConfig]):
    """Упаковывает файлы и каталоги в архив."""

    name: ClassVar[str] = "file"
    description: ClassVar[str] = "Работает с файлами и каталогами"
    config_model: ClassVar[type[FileConfig]] = FileConfig

    # --- Override methods ---

    def process(self, tmp_dir: str | Path, dir_result: str | Path) -> str:
        """Собирает пути из config.path в архив tar.gz.

        Отсутствующие пути пропускаются.

        Args:
            tmp_dir: Каталог для временных файлов. Эта цель его не использует.
            dir_result: Каталог, куда кладется итоговый файл.

        Returns:
            Имя итогового архива в dir_result.

        Raises:
            TargetError: архив не удалось создать.
        """
        archive_name = self._archive_name()
        archive_path = Path(dir_result) / archive_name
        try:
            with tarfile.open(archive_path, "w:gz") as tar:
                for raw_path in self._config_target.path:
                    path = Path(raw_path)
                    if path.exists():
                        tar.add(path)
        except (OSError, tarfile.TarError) as exc:
            raise TargetError(f"ошибка архивации: {exc}") from exc
        return archive_name

    # --- Private methods ---

    def _archive_name(self) -> str:
        """Имя архива цели: имя из настроек, дата и расширение tar.gz.

        Returns:
            Имя вида ``{имя}_{год}.{месяц}.{день}.tar.gz``.
        """
        today = date.today()
        return (
            f"{self._config.name}_{today.year}.{today.month:02d}.{today.day:02d}.tar.gz"
        )
