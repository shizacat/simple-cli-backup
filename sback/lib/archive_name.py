"""Имена файлов архива бэкапа.

Имя архива имеет вид ``{срез}_{год}.{месяц}.{день}.{NNNN}.{расширение}``,
например ``daily_2026.10.26.0000.tar``. Расширение берется из исходного имени.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from sback.lib.exception import ArchiveNameError

# Шаблон имени архива
_ARCHIVE_NAME = re.compile(
    r"^(?P<base>.*_\d{4}\.\d{2}\.\d{2})\.(?P<index>\d{4})\.(?P<ext>.+)\Z"
)
# Шаблон имени архива но без индекса
_ARCHIVE_BASE_NAME = re.compile(
    r"^(?P<base>.*_\d{4}\.\d{2}\.\d{2})\.(?P<ext>(?!\d{4}(?:\.|\Z)).+)\Z"
)


def is_archive_name(file_name: str) -> bool:
    """Проверяет, что имя подходит под шаблон архива бэкапа.

    Returns:
        True, если имя соответствует формату архива.
    """
    return _ARCHIVE_NAME.fullmatch(file_name) is not None


def archiv_name_add_index(file_name: str, existing: Iterable[str]) -> str:
    """Добавляет к имени архива индекс.

    ``file_name`` всегда без индекса: ``{срез}_{год}.{месяц}.{день}.{расширение}``.
    Первая копия этой даты получает ``.0000``. Если копии уже есть,
    индекс на единицу больше максимального. Расширение остается тем,
    что пришло в ``file_name``.

    Args:
        file_name: Имя без индекса.
        existing: Имена, которые уже есть в месте хранения.

    Returns:
        Имя с добавленным индексом ``.{NNNN}`` и исходным расширением.

    Raises:
        ArchiveNameError: ``file_name`` не является именем без индекса.
    """
    base, ext = _source_parts(file_name)
    highest: int | None = None
    for item in existing:
        if not is_archive_name(item):
            continue
        item_base, item_index, item_ext = _parts(item)
        if item_base != base or item_ext != ext:
            continue
        highest = item_index if highest is None else max(highest, item_index)
    index = 0 if highest is None else highest + 1
    return f"{base}.{index:04d}.{ext}"


def _source_parts(file_name: str) -> tuple[str, str]:
    """Основа имени без индекса и его расширение.

    Returns:
        Часть ``{срез}_{год}.{месяц}.{день}`` и расширение из имени.

    Raises:
        ArchiveNameError: имя уже содержит индекс или не содержит дату.
    """
    found = _ARCHIVE_BASE_NAME.fullmatch(file_name)
    if found is None:
        raise ArchiveNameError(
            "имя архива без индекса должно иметь вид "
            f"{{срез}}_{{год}}.{{месяц}}.{{день}}.{{расширение}}: {file_name}"
        )
    return found.group("base"), found.group("ext")


def _parts(file_name: str) -> tuple[str, int, str]:
    """Разбирает имя на основу, индекс и расширение.

    Returns:
        Основа имени, числовой индекс и расширение.

    Raises:
        ArchiveNameError: имя не соответствует формату архива.
    """
    found = _ARCHIVE_NAME.fullmatch(file_name)
    if found is None:
        raise ArchiveNameError(
            "имя архива не соответствует формату "
            f"{{срез}}_{{год}}.{{месяц}}.{{день}}.{{NNNN}}.{{расширение}}: {file_name}"
        )
    return found.group("base"), int(found.group("index")), found.group("ext")
