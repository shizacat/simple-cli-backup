"""Базовый класс уведомлений."""

from __future__ import annotations

from typing import ClassVar, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from sback.lib.config import Notice
from sback.lib.exception import NotifyError

ConfigT = TypeVar("ConfigT", bound=BaseModel)


class NotifyBase(Generic[ConfigT]):
    """Базовый класс уведомления о результате среза.

    Attributes:
        name: Имя типа уведомления. Совпадает с полем type в конфигурации.
        description: Краткое описание канала.
        config_model: Модель поля Notice.config для этого типа.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    config_model: ClassVar[type[ConfigT]]

    def __init__(self, config: Notice):
        """Проверяет настройки канала.

        Args:
            config: Канал из файла настроек.

        Raises:
            NotifyError: для уведомления не задана модель настроек или
                Notice.config ей не соответствует.
        """
        self._config = config
        self._config_notice: ConfigT = self._parse_config(config)

    def _parse_config(self, notice: Notice) -> ConfigT:
        """Собирает настройки канала моделью config_model.

        Args:
            notice: Канал из файла настроек.

        Returns:
            Проверенные настройки конкретного канала.

        Raises:
            NotifyError: модель не задана или Notice.config ей не соответствует.
        """
        model = getattr(type(self), "config_model", None)
        if not isinstance(model, type) or not issubclass(model, BaseModel):
            raise NotifyError("для уведомления не задана модель настроек")
        try:
            return model.model_validate(notice.config)
        except ValidationError as exc:
            raise NotifyError(str(exc)) from exc

    @classmethod
    def factory(cls, config: Notice) -> "NotifyBase":
        """Создает уведомление по полю type в настройках.

        Args:
            config: Канал из файла настроек.

        Returns:
            Экземпляр зарегистрированного уведомления.

        Raises:
            NotifyError: тип уведомления не зарегистрирован или настройки
                ему не соответствуют.
        """
        for subclass in cls.__subclasses__():
            if getattr(subclass, "name", None) is None:
                continue
            if subclass.name == config.type:
                return subclass(config)
        raise NotifyError(f"Object 'notice' of type {config.type} not found")

    def send(self, body: str) -> None:
        """Отправляет текст отчета.

        Args:
            body: Текст отчета о срезе.

        Raises:
            NotImplementedError: тип уведомления не отправляет сообщения.
            NotifyError: сообщение не удалось отправить.
        """
        raise NotImplementedError
