"""Цель бэкапа: архив баз MongoDB."""

from __future__ import annotations

import fnmatch
import subprocess
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from sback.lib.exception import TargetError
from sback.lib.target_base import TargetBase

_SERVER_SELECTION_TIMEOUT_MS = 10_000


class MongodbConfig(BaseModel):
    """Настройки цели mongodb.

    Подключение задается только строкой ``uri``. ``database`` — шаблон
    имени. ``*`` подходит под все базы и стоит по умолчанию.
    """

    uri: str = Field(min_length=1, description="Строка подключения MongoDB")
    database: str = Field(
        default="*",
        min_length=1,
        description="Имя базы или шаблон. * означает все базы",
    )
    mongodump: str = Field(default="mongodump", description="Команда mongodump")


class Mongodb(TargetBase[MongodbConfig]):
    """Снимает архив mongodump для баз, имя которых подходит под шаблон."""

    name: ClassVar[str] = "mongodb"
    description: ClassVar[str] = "Делает архив баз MongoDB"
    config_model: ClassVar[type[MongodbConfig]] = MongodbConfig

    # --- Override methods ---

    def process(self, tmp_dir: Path) -> Iterator[Path]:
        """Пишет архив каждой подходящей базы в временный каталог.

        Для каждой базы вызывается ``mongodump --archive --gzip``.
        Файл называется ``{база}.archive.gz``.

        Args:
            tmp_dir: Временный каталог этой цели.

        Returns:
            Пути архивов баз.

        Raises:
            TargetError: нет подходящих баз, сервер недоступен или mongodump
                завершился ошибкой.
        """
        names = self._matching_databases(self._database_names())
        if not names:
            raise TargetError(f"нет баз по шаблону {self._config_target.database}")
        for name in names:
            yield self._dump_database(name, tmp_dir)

    def _database_names(self) -> list[str]:
        """Читает имена баз с сервера.

        Returns:
            Имена баз, которые видит пользователь подключения.

        Raises:
            TargetError: сервер не ответил.
        """
        try:
            client = self._client()
        except PyMongoError as exc:
            raise TargetError(f"ошибка MongoDB: {exc}") from exc
        try:
            return client.list_database_names()
        except PyMongoError as exc:
            raise TargetError(f"ошибка MongoDB: {exc}") from exc
        finally:
            client.close()

    def _client(self) -> MongoClient[dict[str, Any]]:
        """Открывает клиент по uri.

        Returns:
            Клиент MongoDB. Его нужно закрыть.
        """
        return MongoClient(
            self._config_target.uri,
            serverSelectionTimeoutMS=_SERVER_SELECTION_TIMEOUT_MS,
        )

    def _dump_database(self, database: str, tmp_dir: Path) -> Path:
        """Снимает одну базу в gzip-архив mongodump.

        Args:
            database: Имя базы.
            tmp_dir: Каталог, куда положить архив.

        Returns:
            Путь к файлу ``{база}.archive.gz``.

        Raises:
            TargetError: mongodump не запустился или не создал архив.
        """
        archive = tmp_dir / f"{database}.archive.gz"
        command = self._command(database, archive)
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise TargetError(f"не удалось запустить mongodump: {exc}") from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise TargetError(f"ошибка mongodump: {detail}")
        if not archive.is_file():
            raise TargetError(f"mongodump не создал архив {archive.name}")
        return archive

    def _command(self, database: str, archive: Path) -> list[str]:
        """Собирает аргументы mongodump для одной базы.

        Args:
            database: Имя базы.
            archive: Куда записать архив.

        Returns:
            Команда без оболочки.
        """
        return [
            self._config_target.mongodump,
            "--uri",
            self._config_target.uri,
            "--db",
            database,
            f"--archive={archive}",
            "--gzip",
        ]

    def _matching_databases(self, names: Iterable[str]) -> list[str]:
        """Оставляет имена баз, которые подходят под шаблон из настроек.

        Args:
            names: Имена баз на сервере.

        Returns:
            Подходящие имена в алфавитном порядке.
        """
        pattern = self._config_target.database
        return sorted(name for name in names if fnmatch.fnmatchcase(name, pattern))
