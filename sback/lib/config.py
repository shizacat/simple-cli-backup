"""Модель файла настроек."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ConfigError(Exception):
	"""Файл настроек не удалось прочитать или он не соответствует формату."""


class Place(BaseModel):
	"""Место хранения бэкапа."""

	model_config = ConfigDict(extra="allow")

	name: str
	type: str


class Target(BaseModel):
	"""Цель бэкапа внутри среза."""

	model_config = ConfigDict(extra="allow")

	name: str
	type: str


class Notify(BaseModel):
	"""Ссылка на уведомление в срезе."""

	name: str
	status: Literal["good", "bad"] | None = None


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

	name: str | None = None
	places: list[Place]
	slises: list[Slise]
	notices: list[Notice] = Field(default_factory=list)

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
