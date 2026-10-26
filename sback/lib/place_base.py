"""
Базовый класс для мест хранения бэкапов.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from sback.lib.config import Place
from sback.lib.exception import PlaceError


class PlaceBase:
    """Базовый класс для мест хранения бэкапов.

    Attributes:
        name: Имя места хранения бэкапов.
            Берется из типа плагина в конфигурации.
    """

    name: ClassVar[str]

    def __init__(self, config: Place):
        """Инициализация места хранения бэкапов.

        Args:
            config: Конфигурация места хранения бэкапов.
        """
        self._config = config

    @classmethod
    def factory(cls, config: Place) -> "PlaceBase":
        """Создает место хранения по полю type в настройках.

        Raises:
            PlaceError: тип места не зарегистрирован.
        """
        for subclass in cls.__subclasses__():
            if getattr(subclass, "name", None) is None:
                continue
            if subclass.name == config.type:
                return subclass(config)
        raise PlaceError(f"Object 'place' of type {config.type} not found")

    # --- Override methods ---

    def process(self, result_path: str | Path) -> None:
        """Копирует файл бэкапа в место хранения и запускает ротацию.

        Args:
            result_path: Путь к файлу результата бэкапа,
                именно он будет отправлен в место хранения
        """
        raise NotImplementedError

    def init(self) -> None:
        """
        Инициализация места, если нужна интерактивная настройка.
        Если не требуется, то можно не реализовывать
        """
