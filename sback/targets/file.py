"""Цель бэкапа: файлы и каталоги."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field

from sback.lib.config import Target
from sback.lib.target_base import TargetBase


class FileConfig(BaseModel):
    """Настройки цели file."""

    path: list[str] = Field(min_length=1, description="Файлы и каталоги для архива")


class File(TargetBase[FileConfig]):
    """Отдает файлы и каталоги, которые срез положит в архив."""

    name: ClassVar[str] = "file"
    description: ClassVar[str] = "Работает с файлами и каталогами"
    config_model: ClassVar[type[FileConfig]] = FileConfig

    # --- Override methods ---

    def process(self, tmp_dir: Path) -> Iterator[Path]:
        """Возвращает существующие пути из config.path.

        Отсутствующие пути пропускаются. Временный каталог этой цели не нужен:
        файлы уже лежат на диске.

        Args:
            tmp_dir: Временный каталог этой цели.

        Returns:
            Итератор путей, которые нужно добавить в архив среза.
        """
        for raw_path in self._config_target.path:
            path = Path(raw_path)
            if path.exists():
                yield path
