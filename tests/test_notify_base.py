import pytest
from pydantic import BaseModel

import sback.notices  # регистрация email
from sback.lib.config import Notice
from sback.lib.exception import NotifyError
from sback.lib.notify_base import NotifyBase


def test_factory_rejects_unknown_type() -> None:
    class Nameless(NotifyBase):
        """Подкласс без имени не участвует в выборе типа."""

    with pytest.raises(NotifyError, match="not found"):
        NotifyBase.factory(Notice(name="mail", type="missing", config={}))


def test_factory_requires_config_model() -> None:
    class Bare(NotifyBase):
        name = "bare"
        description = "без модели"

    with pytest.raises(NotifyError, match="модель настроек"):
        NotifyBase.factory(Notice(name="n", type="bare", config={}))


def test_send_is_not_implemented() -> None:
    class ProbeConfig(BaseModel):
        pass

    class Probe(NotifyBase[ProbeConfig]):
        name = "probe"
        description = "probe"
        config_model = ProbeConfig

    channel = NotifyBase.factory(Notice(name="n", type="probe", config={}))
    with pytest.raises(NotImplementedError):
        channel.send("report")


def test_email_is_registered() -> None:
    notice = Notice(
        name="mail",
        type="email",
        config={
            "server": "localhost",
            "to": ["a@example.com"],
            "from": "backup@example.com",
        },
    )

    assert type(NotifyBase.factory(notice)).name == "email"
