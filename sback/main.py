#!/usr/bin/env python3

"""Точка входа Simple CLI Backup."""

import argparse
import sys

from sback import __version__
from sback.lib.backup import Backup
from sback.lib.config import Config
from sback.lib.exception import ArchiveNameError, ConfigError, PlaceError, TargetError


def plugin_info() -> None:
    """Отображает информацию о плагинах (target и place)."""
    import sback.app  # регистрация плагинов
    from sback.base import PlaceBase, TargetBase

    print("Target plugins:")
    for cls in TargetBase.__subclasses__():
        print(f"    {cls.name} - {cls.description}")
    print()
    print("Place plugins:")
    for cls in PlaceBase.__subclasses__():
        print(f"    {cls.name} - {cls.description}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sback",
        description="Simple CLI Backup",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="Show version",
    )
    parser.add_argument(
        "--plugin-info",
        action="store_true",
        help="Displays information about plugins",
    )
    parser.add_argument(
        "--config",
        metavar="config_file",
        help="The path to the file with the settings",
    )
    parser.add_argument(
        "-t",
        "--config-test",
        metavar="config_file",
        help="Testing config file",
    )
    parser.add_argument(
        "init",
        nargs="?",
        choices=["init"],
        metavar="init",
        help="Initializing modules, if necessary",
    )
    return parser


def _validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.init:
        if (
            args.config is None
            or args.version
            or args.plugin_info
            or args.config_test is not None
        ):
            parser.error(
                "init requires --config and cannot be combined with other options"
            )
        return

    modes = sum(
        [
            args.version,
            args.plugin_info,
            args.config is not None,
            args.config_test is not None,
        ]
    )
    if modes != 1:
        parser.error(
            "specify exactly one of --config, -t/--config-test, --plugin-info, or --version"
        )


def _run_backup(config_file: str, *, init: bool = False) -> int:
    """Читает настройки и запускает бэкап.

    Args:
        config_file: Путь к файлу настроек.
        init: Инициализировать места и не выполнять срезы.

    Returns:
        ``0``, если операция завершилась, иначе ``1``.
    """
    config = _read_config(config_file)
    if config is None:
        return 1

    try:
        backup = Backup(config)
    except (ConfigError, PlaceError, TargetError) as exc:
        print(f"Error: \n\t{exc}")
        return 1

    try:
        if init:
            backup.init()
        else:
            backup.process()
    except KeyboardInterrupt:
        print("\nThe operation was interrupted")
        return 0
    except (ArchiveNameError, ConfigError, PlaceError, TargetError) as exc:
        print("[E]", exc)
        return 1

    return 0


def _read_config(config_file: str) -> Config | None:
    """Читает файл настроек и печатает ошибку, если он непригоден.

    Args:
        config_file: Путь к файлу настроек.

    Returns:
        Модель настроек или ``None``, если файл не удалось прочитать.
    """
    try:
        return Config.from_file(config_file)
    except FileNotFoundError:
        print("The file of settings not found")
    except OSError as exc:
        print(f"Error: \n\t{exc}")
    except ConfigError as exc:
        print(f"Error: \n\t{exc}")
    return None


def _check_config(config_file: str) -> int:
    """Проверяет, что файл настроек читается и подходит модели.

    Args:
        config_file: Путь к файлу настроек.

    Returns:
        ``0``, если файл корректен, иначе ``1``.
    """
    if _read_config(config_file) is None:
        return 1

    print("Success")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _validate_args(parser, args)

    # Выводим версию
    if args.version:
        print(__version__)
        return 0

    # Выводим информацию о плагинах
    if args.plugin_info:
        plugin_info()
        return 0

    # Проверяем файл настроек
    if args.config_test is not None:
        return _check_config(args.config_test)

    # Запуск бэкапа
    return _run_backup(config_file=args.config, init=bool(args.init))


if __name__ == "__main__":
    sys.exit(main())
