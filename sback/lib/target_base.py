"""
Базовый класс для целей бэкапа.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from sback.lib.config import Target
from sback.lib.exception import TargetError

ConfigT = TypeVar("ConfigT", bound=BaseModel)


class TargetBase(Generic[ConfigT]):
    """Базовый класс для целей бэкапа.

    Attributes:
        name: Имя типа цели. Совпадает с полем type в конфигурации.
        description: Краткое описание цели для списка плагинов.
        config_model: Модель поля Target.config для этого типа цели.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    config_model: ClassVar[type[ConfigT]]

    def __init__(self, config: Target):
        """Инициализация цели бэкапа.

        Args:
            config: Конфигурация цели бэкапа.

        Raises:
            TargetError: для цели не задана модель настроек или Target.config
                ей не соответствует.
        """
        self._config = config
        self._config_target: ConfigT = self._parse_config(config)

    # --- Private methods ---

    def _parse_config(self, target: Target) -> ConfigT:
        """Собирает настройки цели моделью config_model.

        Returns:
            Проверенные настройки конкретной цели.

        Raises:
            TargetError: модель не задана или Target.config ей не соответствует.
        """
        model = getattr(type(self), "config_model", None)
        if not isinstance(model, type) or not issubclass(model, BaseModel):
            raise TargetError("для цели не задана модель настроек")
        try:
            return model.model_validate(target.config)
        except ValidationError as exc:
            raise TargetError(str(exc)) from exc

    # --- Public methods ---

    @classmethod
    def factory(cls, config: Target) -> "TargetBase":
        """Создает цель по полю type в настройках.

        Returns:
            Экземпляр зарегистрированной цели.

        Raises:
            TargetError: тип цели не зарегистрирован.
        """
        for subclass in cls.__subclasses__():
            if getattr(subclass, "name", None) is None:
                continue
            if subclass.name == config.type:
                return subclass(config)
        raise TargetError(f"Object 'target' of type {config.type} not found")

    # --- Override methods ---

    def process(self, tmp_dir: Path) -> Iterable[Path]:
        """Готовит файлы для архивирования
        Они могут быть как во временном каталоге так и просто передаваться.
        И возвращает их пути.

        ``tmp_dir`` можно использовать для промежуточных файлов.
        Если файл создан там, его путь нужно вернуть из этого метода:
        после выхода каталог удаляется.

        Args:
            tmp_dir: Временный каталог для файлов цели.

        Returns:
            Пути файлов для архива среза. Это может быть список или итератор.

        Raises:
            NotImplementedError: цель не реализована.
            TargetError: цель не смогла подготовить файлы.
        """
        raise NotImplementedError
