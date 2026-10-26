"""Цель бэкапа: дамп баз MySQL."""

from __future__ import annotations

import fnmatch
import subprocess
from collections.abc import Iterable, Iterator
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import ClassVar

import mysql.connector
from mysql.connector import Error
from pydantic import BaseModel, Field

from sback.lib.exception import TargetError
from sback.lib.target_base import TargetBase

_SYSTEM_DATABASES = frozenset(
    {"information_schema", "performance_schema", "mysql", "sys"}
)
_CONNECTION_TIMEOUT = 10


class MysqlConfig(BaseModel):
    """Настройки цели mysql.

    ``database`` — шаблон имени. ``*`` подходит под все пользовательские
    базы и стоит по умолчанию. Служебные базы при ``*`` пропускаются.
    ``mysqldump: true`` отдает запись файла утилите ``mysqldump``.
    """

    host: str = Field(min_length=1, description="Адрес сервера MySQL")
    port: int = Field(default=3306, ge=1, le=65535, description="Порт сервера MySQL")
    user: str = Field(min_length=1, description="Пользователь")
    password: str = Field(default="", description="Пароль")
    charset: str = Field(
        default="utf8mb4",
        pattern=r"^[A-Za-z0-9_]+$",
        description="Кодировка подключения",
    )
    database: str = Field(
        default="*",
        min_length=1,
        description="Имя базы или шаблон. * означает все пользовательские базы",
    )
    mysqldump: bool = Field(
        default=False,
        description="Писать дамп утилитой mysqldump",
    )


class Mysql(TargetBase[MysqlConfig]):
    """Пишет SQL-дамп таблиц для баз, имя которых подходит под шаблон."""

    name: ClassVar[str] = "mysql"
    description: ClassVar[str] = "Делает дамп баз MySQL"
    config_model: ClassVar[type[MysqlConfig]] = MysqlConfig

    # --- Override methods ---

    def process(self, tmp_dir: Path) -> Iterator[Path]:
        """Пишет SQL-дамп каждой подходящей базы во временный каталог.

        Файл называется ``{база}.sql``. Без флага ``mysqldump`` в него попадают
        базовые таблицы: структура и данные. С флагом файл пишет утилита.

        Args:
            tmp_dir: Временный каталог этой цели.

        Returns:
            Пути SQL-файлов.

        Raises:
            TargetError: нет подходящих баз или сервер не отдал дамп.
        """
        names = self._matching_databases(self._database_names())
        if not names:
            raise TargetError(f"нет баз по шаблону {self._config_target.database}")
        for name in names:
            yield self._dump_database(name, tmp_dir)

    # --- Private methods ---

    def _database_names(self) -> list[str]:
        """Читает имена баз с сервера.

        Returns:
            Имена баз, которые видит пользователь подключения.

        Raises:
            TargetError: сервер не ответил.
        """
        try:
            connection = self._connect()
        except Error as exc:
            raise TargetError(f"ошибка MySQL: {exc}") from exc
        try:
            cursor = connection.cursor()
            try:
                cursor.execute("SHOW DATABASES")
                return [self._text(row[0]) for row in cursor.fetchall()]
            finally:
                cursor.close()
        except Error as exc:
            raise TargetError(f"ошибка MySQL: {exc}") from exc
        finally:
            connection.close()

    def _connect(self, database: str | None = None) -> mysql.connector.MySQLConnection:
        """Открывает подключение к серверу.

        Args:
            database: База, которую выбрать сразу. Без аргумента база не выбрана.

        Returns:
            Открытое подключение. Его нужно закрыть.
        """
        settings: dict[str, object] = {
            "host": self._config_target.host,
            "port": self._config_target.port,
            "user": self._config_target.user,
            "password": self._config_target.password,
            "charset": self._config_target.charset,
            "connection_timeout": _CONNECTION_TIMEOUT,
            "use_pure": True,
        }
        if database is not None:
            settings["database"] = database
        return mysql.connector.connect(**settings)

    def _dump_database(self, database: str, tmp_dir: Path) -> Path:
        """Снимает одну базу в SQL-файл.

        Args:
            database: Имя базы.
            tmp_dir: Каталог, куда положить файл.

        Returns:
            Путь к файлу ``{база}.sql``.

        Raises:
            TargetError: дамп не удался.
        """
        path = tmp_dir / f"{database}.sql"
        if self._config_target.mysqldump:
            self._dump_with_utility(database, path)
            return path
        try:
            connection = self._connect(database)
        except Error as exc:
            raise TargetError(f"ошибка MySQL: {exc}") from exc
        try:
            cursor = connection.cursor()
            try:
                script = self._script(cursor, database)
            finally:
                cursor.close()
        except Error as exc:
            raise TargetError(f"ошибка MySQL: {exc}") from exc
        finally:
            connection.close()
        path.write_text(script, encoding="utf-8")
        return path

    def _dump_with_utility(self, database: str, path: Path) -> None:
        """Снимает одну базу утилитой mysqldump.

        Args:
            database: Имя базы.
            path: Куда записать SQL.

        Raises:
            TargetError: утилита не запустилась или не создала файл.
        """
        command = [
            "mysqldump",
            f"--host={self._config_target.host}",
            f"--port={self._config_target.port}",
            f"--user={self._config_target.user}",
            f"--default-character-set={self._config_target.charset}",
            "--single-transaction",
            "--routines",
            "--triggers",
            "--events",
            f"--result-file={path}",
            database,
        ]
        if self._config_target.password:
            command.insert(4, f"--password={self._config_target.password}")
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise TargetError(f"не удалось запустить mysqldump: {exc}") from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise TargetError(f"ошибка mysqldump: {detail}")
        if not path.is_file():
            raise TargetError(f"mysqldump не создал архив {path.name}")

    def _script(self, cursor: mysql.connector.cursor.MySQLCursor, database: str) -> str:
        """Собирает текст дампа одной базы.

        Args:
            cursor: Курсор выбранной базы.
            database: Имя базы.

        Returns:
            Текст SQL-дампа.
        """
        lines = [
            "-- Simple CLI Backup",
            f"-- Host: {self._config_target.host}    Database: {database}",
            f"SET NAMES {self._config_target.charset};",
            "SET FOREIGN_KEY_CHECKS=0;",
            "",
        ]
        cursor.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
        tables = [
            self._text(row[0])
            for row in cursor.fetchall()
            if len(row) < 2 or self._text(row[1]) == "BASE TABLE"
        ]
        for table in tables:
            lines.extend(self._table_dump(cursor, table))
        lines.append("SET FOREIGN_KEY_CHECKS=1;")
        lines.append("")
        return "\n".join(lines)

    def _table_dump(
        self, cursor: mysql.connector.cursor.MySQLCursor, table: str
    ) -> list[str]:
        """Собирает структуру и строки одной таблицы.

        Args:
            cursor: Курсор выбранной базы.
            table: Имя таблицы.

        Returns:
            Строки SQL для этой таблицы.

        Raises:
            TargetError: сервер не вернул CREATE TABLE.
        """
        quoted = self._quote_ident(table)
        cursor.execute(f"SHOW CREATE TABLE {quoted}")
        row = cursor.fetchone()
        if row is None or row[1] is None:
            raise TargetError(f"не удалось получить структуру таблицы {table}")
        lines = [
            f"-- Table structure for table {quoted}",
            "",
            f"DROP TABLE IF EXISTS {quoted};",
            f"{self._text(row[1])};",
            "",
            f"-- Dumping data for table {quoted}",
            "",
        ]
        cursor.execute(f"SELECT * FROM {quoted}")
        values = [
            "(" + ", ".join(self._sql_literal(value) for value in record) + ")"
            for record in cursor.fetchall()
        ]
        if values:
            lines.append(f"LOCK TABLES {quoted} WRITE;")
            lines.append(f"INSERT INTO {quoted} VALUES {', '.join(values)};")
            lines.append("UNLOCK TABLES;")
            lines.append("")
        return lines

    def _matching_databases(self, names: Iterable[str]) -> list[str]:
        """Оставляет имена баз, которые подходят под шаблон из настроек.

        Args:
            names: Имена баз на сервере.

        Returns:
            Подходящие имена в алфавитном порядке.
        """
        pattern = self._config_target.database
        matched = [name for name in names if fnmatch.fnmatchcase(name, pattern)]
        if pattern == "*":
            matched = [name for name in matched if name not in _SYSTEM_DATABASES]
        return sorted(matched)

    def _quote_ident(self, name: str) -> str:
        """Заключает имя в обратные кавычки.

        Args:
            name: Имя базы или таблицы.

        Returns:
            Имя, безопасное для подстановки в SQL.
        """
        return "`" + name.replace("`", "``") + "`"

    def _text(self, value: object) -> str:
        """Превращает ответ сервера в строку.

        Args:
            value: Значение из курсора.

        Returns:
            Текст в UTF-8.
        """
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)

    def _sql_literal(self, value: object) -> str:
        """Форматирует значение как литерал SQL.

        Args:
            value: Значение ячейки.

        Returns:
            Фрагмент SQL: NULL, число или строка в кавычках.
        """
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, Decimal)):
            return str(value)
        if isinstance(value, float):
            return repr(value)
        if isinstance(value, (bytes, bytearray)):
            return "X'" + bytes(value).hex() + "'"
        if isinstance(value, datetime):
            return "'" + value.strftime("%Y-%m-%d %H:%M:%S") + "'"
        if isinstance(value, date):
            return "'" + value.isoformat() + "'"
        if isinstance(value, timedelta):
            return "'" + str(value) + "'"
        text = str(value)
        text = (
            text.replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace("\0", "\\0")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )
        return "'" + text + "'"
