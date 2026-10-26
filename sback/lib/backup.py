"""Запуск бэкапа по срезам."""

from __future__ import annotations

import tarfile
import tempfile
from pathlib import Path

import sback.places  # регистрация мест
import sback.targets  # регистрация целей
from sback.lib.archive_name import archive_base_name
from sback.lib.config import Config, Place, Target
from sback.lib.exception import ConfigError, TargetError
from sback.lib.place_base import PlaceBase
from sback.lib.target_base import TargetBase


class Backup:
    """Проверяет настройки и выполняет срезы."""

    def __init__(self, config: Config):
        """Проверяет места и цели из настроек.

        Args:
            config: Файл настроек.

        Raises:
            ConfigError: срез ссылается на неизвестное место.
            PlaceError: место не удалось создать.
            TargetError: цель не удалось создать.
        """
        self._config = config
        self.check()

    def check(self) -> None:
        """Проверяет, что места и цели из срезов можно создать.

        Raises:
            ConfigError: срез ссылается на неизвестное место.
            PlaceError: место не удалось создать.
            TargetError: цель не удалось создать.
        """
        for place in self._config.places:
            PlaceBase.factory(place)
        for slise in self._config.slises:
            for target in slise.target:
                TargetBase.factory(target)
            for place_name in slise.place:
                self._place(place_name)

    def init(self) -> None:
        """Запускает инициализацию мест, если она им нужна."""
        for place in self._config.places:
            PlaceBase.factory(place).init()

    def process(self) -> None:
        """Выполняет все срезы: цели, общий архив и копирование в места.

        Raises:
            ArchiveNameError: имя архива среза не подходит месту хранения.
            PlaceError: файл не удалось скопировать или удалить при ротации.
            TargetError: цель или сборка архива среза завершились ошибкой.
        """
        for slise in self._config.slises:
            with tempfile.TemporaryDirectory() as result_dir:
                archive = self._pack_slise(
                    targets=slise.target,
                    result_dir=Path(result_dir),
                    slise_name=slise.name,
                )
                if archive is None:
                    continue
                for place_name in slise.place:
                    PlaceBase.factory(self._place(place_name)).process(archive)

    def _place(self, name: str) -> Place:
        """Возвращает место по имени из настроек.

        Returns:
            Настройки места.

        Raises:
            ConfigError: места с таким именем нет.
        """
        for place in self._config.places:
            if place.name == name:
                return place
        raise ConfigError(f"для среза не найдено место: {name}")

    def _pack_slise(
        self, targets: list[Target], result_dir: Path, slise_name: str
    ) -> Path | None:
        """Упаковывает файлы целей среза в tar.gz.

        Для каждой цели создается свой временный каталог. Тип архива выбирает
        срез: сейчас это tar.gz.

        Args:
            targets: Цели среза, чьи файлы нужно упаковать.
            result_dir: Каталог, куда положить архив среза.
            slise_name: Имя среза. Входит в имя архива.

        Returns:
            Путь к архиву без индекса или None, если цели не отдали файлов.

        Raises:
            TargetError: цель или сборка архива завершились ошибкой.
        """
        archive = result_dir / archive_base_name(slise_name, "tar.gz")
        has_files = False
        try:
            with tarfile.open(archive, "w:gz") as tar:
                for target in targets:
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        produced = TargetBase.factory(target).process(Path(tmp_dir))
                        for file in produced:
                            path = Path(file)
                            tar.add(path, arcname=path.name)
                            has_files = True
        except (OSError, tarfile.TarError) as exc:
            raise TargetError(f"ошибка сборки среза: {exc}") from exc
        if not has_files:
            archive.unlink(missing_ok=True)
            return None
        return archive
