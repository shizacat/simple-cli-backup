"""Текст отчета о результате среза."""

from enum import Enum


class Status(Enum):
    """Итог цели, места или всего среза."""

    GOOD = "good"
    BAD = "bad"


class Notification:
    """Собирает текст отчета по целям и местам одного среза."""

    def __init__(self, slise_name: str):
        """Запоминает имя среза, для которого строится отчет.

        Args:
            slise_name: Имя среза.
        """
        self.slise_name = slise_name
        self._targets: list[tuple[str, Status, str]] = []
        self._places: list[tuple[str, Status, str]] = []
        self.error: Exception | None = None

    def add_target(self, name: str, status: Status, description: str = "") -> None:
        """Добавляет строку о цели.

        Args:
            name: Имя цели.
            status: Итог этой цели.
            description: Пояснение к итогу. Для ошибки это ее текст.
        """
        self._targets.append((name, status, description))

    def add_place(self, name: str, status: Status, description: str = "") -> None:
        """Добавляет строку о месте хранения.

        Args:
            name: Имя места хранения.
            status: Итог копирования в это место.
            description: Пояснение к итогу. Для ошибки это ее текст.
        """
        self._places.append((name, status, description))

    def fail(self, exc: Exception) -> None:
        """Запоминает первую ошибку среза.

        Args:
            exc: Ошибка цели, сборки архива или места хранения.
        """
        if self.error is None:
            self.error = exc

    @property
    def status(self) -> Status:
        """Возвращает итог среза.

        Returns:
            ``bad``, если хотя бы одна цель или место завершились ошибкой,
            иначе ``good``.
        """
        items = self._targets + self._places
        if any(status is Status.BAD for _, status, _ in items):
            return Status.BAD
        return Status.GOOD

    def body(self) -> str:
        """Собирает текст письма.

        Returns:
            Отчет: итог среза, затем строки целей и мест.
        """
        label = self._label(self.status)
        return (
            f"{self.slise_name} - {label}\n"
            "The target:\n"
            f"{self._lines(self._targets)}\n"
            "Backup Locations:\n"
            f"{self._lines(self._places)}"
        )

    def _lines(self, items: list[tuple[str, Status, str]]) -> str:
        """Собирает строки списка.

        Args:
            items: Имя, итог и пояснение.

        Returns:
            Строки списка. У каждой строки свой итог.
        """
        return "".join(
            f"    * {name} - {self._label(status)}. {description}\n"
            for name, status, description in items
        )

    def _label(self, status: Status) -> str:
        """Возвращает подпись итога.

        Args:
            status: Итог цели, места или среза.

        Returns:
            ``Success`` или ``Error``.
        """
        if status is Status.GOOD:
            return "Success"
        return "Error"
