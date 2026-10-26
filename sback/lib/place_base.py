"""
Базовый класс для мест хранения бэкапов.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from sback.lib.config import Place
from sback.lib.exception import PlaceError

ConfigT = TypeVar("ConfigT", bound=BaseModel)


class PlaceBase(Generic[ConfigT]):
    """Базовый класс для мест хранения бэкапов.

    Attributes:
        name: Имя типа места. Совпадает с полем type в конфигурации.
        description: Краткое описание места для списка плагинов.
        config_model: Модель поля Place.config для этого типа места.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    config_model: ClassVar[type[ConfigT]]

    def __init__(self, config: Place):
        """Инициализация места хранения бэкапов.

        Args:
            config: Конфигурация места хранения бэкапов.

        Raises:
            PlaceError: для места не задана модель настроек или Place.config
                ей не соответствует.
        """
        # Хранит конфигурацию места целиком
        self._config = config
        # Хранит конфигурацию данного метса
        self._config_place: ConfigT = self._parse_config(config)

    # --- Private methods ---

    def _parse_config(self, place: Place) -> ConfigT:
        """Собирает настройки места моделью config_model.

        Raises:
            PlaceError: модель не задана или Place.config ей не соответствует.
        """
        model = getattr(type(self), "config_model", None)
        if not isinstance(model, type) or not issubclass(model, BaseModel):
            raise PlaceError("для места не задана модель настроек")
        try:
            return model.model_validate(place.config)
        except ValidationError as exc:
            raise PlaceError(str(exc)) from exc

    # --- Public methods ---

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

    def rotate(self) -> None:
        """Удаляет самые старые файлы, если их больше rotate.count.

        Raises:
            PlaceError: файл не удалось удалить.
        """
        if self._config.rotate is None:
            return
        names = self.list_files()
        extra = len(names) - self._config.rotate.count
        if extra <= 0:
            return
        for name in sorted(names)[:extra]:
            self.delete_file(name)

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

    def list_files(self) -> list[str]:
        """Имена файлов бэкапа в месте хранения.

        Returns:
            Список имен файлов, которые участвуют в ротации.

        Raises:
            NotImplementedError: место не возвращает список файлов.
        """
        raise NotImplementedError

    def delete_file(self, file_name: str) -> None:
        """Удаляет файл из места хранения.

        Args:
            file_name: Имя файла из list_files.

        Raises:
            NotImplementedError: место не удаляет файлы.
            PlaceError: файл не удалось удалить.
        """
        raise NotImplementedError
