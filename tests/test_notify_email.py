import smtplib
from unittest.mock import MagicMock

import pytest

from sback.lib.config import Notice
from sback.lib.exception import NotifyError
from sback.notices.email import Email


def _notice(**config: object) -> Notice:
    payload = {
        "server": "localhost",
        "to": ["a@example.com"],
        "from": "backup@example.com",
    }
    payload.update(config)
    return Notice(name="mail", type="email", config=payload)


def test_send_uses_starttls_and_login(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    smtp = MagicMock(return_value=client)
    ssl = MagicMock()
    monkeypatch.setattr("sback.notices.email.smtplib.SMTP", smtp)
    monkeypatch.setattr("sback.notices.email.smtplib.SMTP_SSL", ssl)

    Email(
        _notice(
            server="smtp.example.com:587",
            password="secret",
            starttls=True,
            to=["a@example.com", "b@example.com"],
            subject="Backup",
        )
    ).send("report")

    smtp.assert_called_once_with("smtp.example.com", 587, timeout=20)
    ssl.assert_not_called()
    client.starttls.assert_called_once()
    client.login.assert_called_once_with("backup@example.com", "secret")
    assert client.sendmail.call_count == 2
    client.quit.assert_called_once()
    message = client.sendmail.call_args_list[0].args[2]
    assert "Subject: Backup" in message
    assert "To: a@example.com" in message


def test_send_uses_ssl_without_login(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    ssl = MagicMock(return_value=client)
    smtp = MagicMock()
    monkeypatch.setattr("sback.notices.email.smtplib.SMTP_SSL", ssl)
    monkeypatch.setattr("sback.notices.email.smtplib.SMTP", smtp)

    Email(_notice(server="smtp.example.com", ssl=True, starttls=True)).send("report")

    ssl.assert_called_once_with("smtp.example.com", 25, timeout=20)
    smtp.assert_not_called()
    client.starttls.assert_not_called()
    client.login.assert_not_called()
    client.quit.assert_called_once()


def test_send_wraps_smtp_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.sendmail.side_effect = smtplib.SMTPException("rejected")
    monkeypatch.setattr(
        "sback.notices.email.smtplib.SMTP", MagicMock(return_value=client)
    )

    with pytest.raises(NotifyError, match="ошибка email: rejected"):
        Email(_notice()).send("report")

    client.quit.assert_called_once()


def test_quit_error_does_not_hide_sent_mail(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.quit.side_effect = smtplib.SMTPException("bye")
    monkeypatch.setattr(
        "sback.notices.email.smtplib.SMTP", MagicMock(return_value=client)
    )

    Email(_notice()).send("report")

    client.sendmail.assert_called_once()


def test_connect_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sback.notices.email.smtplib.SMTP", MagicMock(side_effect=OSError("down"))
    )

    with pytest.raises(NotifyError, match="ошибка email: down"):
        Email(_notice()).send("report")


def test_config_requires_sender_and_port() -> None:
    with pytest.raises(NotifyError):
        Email(
            Notice(
                name="mail",
                type="email",
                config={"server": "localhost", "to": ["a@example.com"]},
            )
        )

    with pytest.raises(NotifyError, match="host:port"):
        Email(_notice(server="localhost:70000"))
