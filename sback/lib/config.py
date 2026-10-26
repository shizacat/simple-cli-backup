"""Модель файла настроек.

Пример:

.. code-block:: yaml

    places:
      - name: local
        type: folder
        path: /var/backups
        rotate:
          count: 6

    notices:
      - name: mail
        type: email

    slises:
      - name: daily
        place:
          - local
        target:
          - name: files
            type: file
            path:
              - /etc
        notify:
          - name: mail
            status: bad
    
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from sback.lib.exception import ConfigError


class Place(BaseModel):
    """Место хранения бэкапа."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(description="Имя места хранения")
    type: str = Field(description="Тип плагина place")


class Target(BaseModel):
    """Цель бэкапа внутри среза."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(description="Имя цели")
    type: str = Field(description="Тип плагина target")


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
    """Канал уведомлений."""

    model_config = ConfigDict(extra="allow")

    name: str
    type: str


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
