"""Модель файла настроек.

Пример:

.. code-block:: yaml

    places:
      - name: local
        type: folder
        rotate:
          count: 6
        config:
          path: /var/backups

    notices:
      - name: mail
        type: email
        config:
          server: localhost
          to:
            - a@example.com
          from: backup@example.com

    slises:
      - name: daily
        place:
          - local
        target:
          - name: files
            type: file
            config:
              path:
                - /etc
        notify:
          - name: mail
            status: bad

"""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from sback.lib.exception import ConfigError


class Rotate(BaseModel):
    """Сколько копий хранить в месте."""

    count: int = Field(strict=True, description="Сколько последних копий оставлять")


class Place(BaseModel):
    """Место хранения бэкапа.

    Поле config проверяется моделью, которую задает класс места
    через PlaceBase.config_model.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Имя места хранения")
    type: str = Field(description="Тип плагина place")
    rotate: Rotate | None = Field(
        default=None,
        description="Ротация копий. Без поля хранятся все файлы",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Настройки конкретного места",
    )


class Target(BaseModel):
    """Цель бэкапа внутри среза.

    Поле config проверяется моделью, которую задает класс цели
    через TargetBase.config_model.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Имя цели")
    type: str = Field(description="Тип плагина target")
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Настройки конкретной цели",
    )


class Notify(BaseModel):
    """Ссылка на уведомление в срезе."""

    name: str = Field(description="Имя канала уведомлений")
    status: Literal["good", "bad"] | None = Field(
        default=None,
        description="Статус, при котором отправлять уведомление: good или bad",
    )


class Slise(BaseModel):
    """Срез: набор целей и мест, куда складывается результат."""

    model_config = ConfigDict(extra="allow")

    name: str
    place: list[str] = Field(min_length=1)
    target: list[Target]
    notify: list[Notify] = Field(default_factory=list)


class Notice(BaseModel):
    """Канал уведомлений.

    Поле config проверяется моделью, которую задает класс уведомления
    через NotifyBase.config_model.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Имя канала уведомлений")
    type: str = Field(description="Тип плагина notify")
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Настройки конкретного канала",
    )


class Config(BaseModel):
    """Файл настроек."""

    model_config = ConfigDict(extra="allow")

    name: str | None = Field(default=None, description="Имя конфигурации")
    places: list[Place] = Field(description="Места хранения бэкапов")
    slises: list[Slise] = Field(
        description="Срезы: цели и места, куда складывается результат"
    )
    notices: list[Notice] = Field(
        default_factory=list,
        description="Каналы уведомлений",
    )

    @classmethod
    def from_file(cls, config_file: str | Path) -> "Config":
        """Читает файл настроек и собирает модель.

        Raises:
            FileNotFoundError: файла нет.
            ConfigError: файл не является корректным YAML или не проходит проверку.
        """
        path = Path(config_file)
        if not path.is_file():
            raise FileNotFoundError(config_file)
        return cls.from_yaml(path.read_text(encoding="utf-8"))

    @classmethod
    def from_yaml(cls, content: str) -> "Config":
        """Собирает модель из текста YAML.

        Raises:
            ConfigError: текст не является корректным YAML или не проходит проверку.
        """
        try:
            loaded = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise ConfigError(str(exc)) from exc

        try:
            return cls.model_validate(loaded)
        except ValidationError as exc:
            raise ConfigError(str(exc)) from exc
