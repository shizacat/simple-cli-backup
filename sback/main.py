#!/usr/bin/env python3

"""Точка входа Simple CLI Backup."""

import argparse
import os
import sys

import yaml

from sback import __version__


def read_file_config(config_file: str) -> dict:
	"""Читает файл настроек.

	Returns:
		Содержимое файла в виде словаря.
	"""
	if not os.path.isfile(config_file):
		print("The file of settings not found")
		sys.exit(1)

	with open(config_file, encoding="utf-8") as config:
		return yaml.load(config, Loader=yaml.FullLoader)


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
			parser.error("init requires --config and cannot be combined with other options")
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
			"specify exactly one of --config, --config-test, --plugin-info, or --version"
		)


def main(argv: list[str] | None = None) -> int:
	parser = build_parser()
	args = parser.parse_args(argv)
	_validate_args(parser, args)

	if args.version:
		print(__version__)
		return 0

	if args.plugin_info:
		plugin_info()
		return 0

	config_file = args.config_test if args.config_test is not None else args.config
	config = read_file_config(config_file)

	from sback.app import scb
	from sback.exception import ScbException

	if args.config_test is not None:
		try:
			scb(config=config)
		except ScbException as exc:
			print(f"Error: \n\t{exc}")
			return 1
		else:
			print("Success")
		return 0

	try:
		service = scb(config=config)
		if args.init:
			service.init()
		else:
			service.process()
	except KeyboardInterrupt:
		print("\nThe operation was interrupted")
		return 0
	except ScbException as exc:
		print("[E]", exc)
		return 1

	return 0


if __name__ == "__main__":
	sys.exit(main())
