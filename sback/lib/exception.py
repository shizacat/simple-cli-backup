"""Исключения Simple CLI Backup."""


class ConfigError(Exception):
    """Файл настроек не удалось прочитать или он не соответствует формату."""


class PlaceError(Exception):
    """Место хранения не удалось создать."""
