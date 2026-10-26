"""Исключения Simple CLI Backup."""


class ConfigError(Exception):
    """Файл настроек не удалось прочитать или он не соответствует формату."""


class PlaceError(Exception):
    """Ошибка места хранения."""


class TargetError(Exception):
    """Ошибка цели бэкапа."""


class ArchiveNameError(Exception):
    """Имя архива не соответствует формату {срез}_{год}.{месяц}.{день}.{NNNN}.tar."""


class NotifyError(Exception):
    """Ошибка уведомления."""
