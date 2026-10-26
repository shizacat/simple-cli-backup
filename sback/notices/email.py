"""Уведомление по электронной почте."""

from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sback.lib.config import Notice
from sback.lib.exception import NotifyError
from sback.lib.notify_base import NotifyBase


class EmailConfig(BaseModel):
    """Настройки канала email."""

    model_config = ConfigDict(populate_by_name=True)

    server: str = Field(min_length=1, description="Адрес SMTP, host или host:port")
    to: list[str] = Field(min_length=1, description="Получатели")
    sender: str = Field(
        alias="from",
        min_length=1,
        description="Адрес отправителя и логин SMTP",
    )
    password: str | None = Field(default=None, description="Пароль SMTP")
    starttls: bool = Field(default=False, description="Включить STARTTLS")
    ssl: bool = Field(default=False, description="Подключаться по SMTP SSL")
    subject: str = Field(
        default="---= Backup info =---",
        description="Тема письма",
    )

    @field_validator("server")
    @classmethod
    def _check_server(cls, value: str) -> str:
        """Проверяет, что server задан как host или host:port.

        Args:
            value: Значение поля server.

        Returns:
            Тот же адрес, если он записан верно.

        Raises:
            ValueError: в адресе нет хоста или порт вне диапазона 1–65535.
        """
        host, separator, port = value.rpartition(":")
        if not separator:
            return value
        if not host or not port.isdigit() or not 1 <= int(port) <= 65535:
            raise ValueError("адрес SMTP должен быть host или host:port")
        return value


class Email(NotifyBase[EmailConfig]):
    """Отправляет отчет о срезе по SMTP."""

    name: ClassVar[str] = "email"
    description: ClassVar[str] = "Отправляет отчет по почте"
    config_model: ClassVar[type[EmailConfig]] = EmailConfig

    def __init__(self, config: Notice):
        """Проверяет настройки SMTP.

        Args:
            config: Канал из файла настроек. В config нужны server, to и from.

        Raises:
            NotifyError: настройки не соответствуют модели.
        """
        super().__init__(config)

    def send(self, body: str) -> None:
        """Отправляет отчет каждому получателю.

        Args:
            body: Текст отчета о срезе.

        Raises:
            NotifyError: сервер SMTP недоступен или отклонил письмо.
        """
        host, port = self._address()
        settings = self._config_notice
        client: smtplib.SMTP | None = None
        try:
            if settings.ssl:
                client = smtplib.SMTP_SSL(host, port, timeout=20)
            else:
                client = smtplib.SMTP(host, port, timeout=20)
                if settings.starttls:
                    client.ehlo()
                    client.starttls()
                    client.ehlo()
            if settings.password:
                client.login(settings.sender, settings.password)
            for recipient in settings.to:
                message = MIMEText(body)
                message["Subject"] = settings.subject
                message["From"] = settings.sender
                message["To"] = recipient
                client.sendmail(settings.sender, [recipient], message.as_string())
        except (OSError, smtplib.SMTPException) as exc:
            raise NotifyError(f"ошибка email: {exc}") from exc
        finally:
            if client is not None:
                try:
                    client.quit()
                except (OSError, smtplib.SMTPException):
                    pass

    def _address(self) -> tuple[str, int]:
        """Разбирает server на хост и порт.

        Returns:
            Хост и порт. Если порт не указан, используется 25.
        """
        server = self._config_notice.server
        host, separator, port = server.rpartition(":")
        if separator and port.isdigit():
            return host, int(port)
        return server, 25
