"""Цели бэкапа."""

from sback.targets.file import File
from sback.targets.mongodb import Mongodb
from sback.targets.mysql import Mysql

__all__ = ["File", "Mongodb", "Mysql"]
