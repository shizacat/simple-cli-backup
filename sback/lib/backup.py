"""Запуск бэкапа по срезам."""

from __future__ import annotations

import tarfile
import tempfile
from pathlib import Path

import sback.notices  # регистрация уведомлений
import sback.places  # регистрация мест
import sback.targets  # регистрация целей
from sback.lib.archive_name import archive_base_name
from sback.lib.config import Config, Notice, Place, Slise, Target
from sback.lib.exception import (
    ArchiveNameError,
    ConfigError,
    NotifyError,
    PlaceError,
    TargetError,
)
from sback.lib.notification import Notification, Status
from sback.lib.notify_base import NotifyBase
from sback.lib.place_base import PlaceBase
from sback.lib.target_base import TargetBase


class Backup:
    """Проверяет настройки и выполняет срезы."""

    def __init__(self, config: Config):
        """Проверяет места, цели и уведомления из настроек.

        Args:
            config: Файл настроек.

        Raises:
            ConfigError: срез ссылается на неизвестное место или канал.
            NotifyError: уведомление не удалось создать.
            PlaceError: место не удалось создать.
            TargetError: цель не удалось создать.
        """
        self._config = config
        self.check()

    def check(self) -> None:
        """Проверяет, что места, цели и уведомления из срезов можно создать.

        Raises:
            ConfigError: срез ссылается на неизвестное место или канал.
            NotifyError: уведомление не удалось создать.
            PlaceError: место не удалось создать.
            TargetError: цель не удалось создать.
        """
        for place in self._config.places:
            PlaceBase.factory(place)
        for notice in self._config.notices:
            NotifyBase.factory(notice)
        for slise in self._config.slises:
            for target in slise.target:
                TargetBase.factory(target)
            for place_name in slise.place:
                self._place(place_name)
            for item in slise.notify:
                self._notice(item.name)

    def init(self) -> None:
        """Запускает инициализацию мест, если она им нужна."""
        for place in self._config.places:
            PlaceBase.factory(place).init()

    def process(self) -> None:
        """Выполняет все срезы: цели, общий архив и копирование в места.

        Raises:
            ArchiveNameError: имя архива среза не подходит месту хранения.
            NotifyError: уведомление не удалось отправить.
            PlaceError: файл не удалось скопировать или удалить при ротации.
            TargetError: цель или сборка архива среза завершились ошибкой.
        """
        errors: list[Exception] = []
        for slise in self._config.slises:
            report = Notification(slise.name)
            with tempfile.TemporaryDirectory() as result_dir:
                archive = self._pack_slise(
                    targets=slise.target,
                    result_dir=Path(result_dir),
                    slise_name=slise.name,
                    report=report,
                )
                if archive is not None:
                    for place_name in slise.place:
                        self._copy_place(place_name, archive, report)
            if report.error is not None:
                errors.append(report.error)
            try:
                self._notify(slise, report)
            except NotifyError as exc:
                errors.append(exc)
        if errors:
            raise errors[0]

    def _place(self, name: str) -> Place:
        """Возвращает место по имени из настроек.

        Args:
            name: Имя места хранения.

        Returns:
            Настройки места.

        Raises:
            ConfigError: места с таким именем нет.
        """
        for place in self._config.places:
            if place.name == name:
                return place
        raise ConfigError(f"для среза не найдено место: {name}")

    def _notice(self, name: str) -> Notice:
        """Возвращает канал уведомлений по имени из настроек.

        Args:
            name: Имя канала.

        Returns:
            Настройки канала.

        Raises:
            ConfigError: канала с таким именем нет.
        """
        for notice in self._config.notices:
            if notice.name == name:
                return notice
        raise ConfigError(f"для среза не найден канал уведомлений: {name}")

    def _copy_place(self, place_name: str, archive: Path, report: Notification) -> None:
        """Копирует архив среза в место и записывает итог в отчет.

        Args:
            place_name: Имя места хранения.
            archive: Архив среза без индекса.
            report: Отчет, куда записать итог копирования.
        """
        try:
            PlaceBase.factory(self._place(place_name)).process(archive)
        except (ArchiveNameError, ConfigError, PlaceError) as exc:
            report.add_place(place_name, Status.BAD, str(exc))
            report.fail(exc)
        else:
            report.add_place(place_name, Status.GOOD)

    def _notify(self, slise: Slise, report: Notification) -> None:
        """Отправляет отчет среза в подходящие каналы.

        Канал со статусом получает отчет только при том же итоге среза.
        Канал без статуса получает отчет всегда.

        Args:
            slise: Срез, для которого собран отчет.
            report: Итог целей и мест этого среза.

        Raises:
            NotifyError: канал не удалось создать или отправка не удалась.
            ConfigError: срез ссылается на неизвестный канал.
        """
        error: NotifyError | None = None
        for item in slise.notify:
            if item.status is not None and item.status != report.status.value:
                continue
            try:
                NotifyBase.factory(self._notice(item.name)).send(report.body())
            except NotifyError as exc:
                if error is None:
                    error = exc
        if error is not None:
            raise error

    def _pack_slise(
        self,
        targets: list[Target],
        result_dir: Path,
        slise_name: str,
        report: Notification,
    ) -> Path | None:
        """Упаковывает файлы целей среза в tar.gz.

        Для каждой цели создается свой временный каталог. Тип архива выбирает
        срез: сейчас это tar.gz.

        Args:
            targets: Цели среза, чьи файлы нужно упаковать.
            result_dir: Каталог, куда положить архив среза.
            slise_name: Имя среза. Входит в имя архива.
            report: Отчет, куда записать итог каждой цели.

        Returns:
            Путь к архиву без индекса или None, если цели не отдали файлов.
        """
        archive = result_dir / archive_base_name(slise_name, "tar.gz")
        has_files = False
        try:
            tar = tarfile.open(archive, "w:gz")
        except (OSError, tarfile.TarError) as exc:
            self._fail_targets(targets, report, exc)
            archive.unlink(missing_ok=True)
            return None
        with tar:
            for target in targets:
                try:
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        produced = TargetBase.factory(target).process(Path(tmp_dir))
                        for file in produced:
                            path = Path(file)
                            tar.add(path, arcname=path.name)
                            has_files = True
                except TargetError as exc:
                    report.add_target(target.name, Status.BAD, str(exc))
                    report.fail(exc)
                except (OSError, tarfile.TarError) as exc:
                    wrapped = TargetError(f"ошибка сборки среза: {exc}")
                    report.add_target(target.name, Status.BAD, str(wrapped))
                    report.fail(wrapped)
                else:
                    report.add_target(target.name, Status.GOOD)
        if not has_files:
            archive.unlink(missing_ok=True)
            return None
        return archive

    def _fail_targets(
        self, targets: list[Target], report: Notification, exc: Exception
    ) -> None:
        """Помечает все цели среза ошибкой сборки архива.

        Args:
            targets: Цели, которые не удалось упаковать.
            report: Отчет среза.
            exc: Ошибка открытия архива.
        """
        wrapped = TargetError(f"ошибка сборки среза: {exc}")
        for target in targets:
            report.add_target(target.name, Status.BAD, str(wrapped))
        report.fail(wrapped)
