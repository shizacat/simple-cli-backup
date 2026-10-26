import pytest

from sback.lib.config import Target
from sback.lib.exception import TargetError
from sback.lib.target_base import TargetBase


def test_factory_unknown_type() -> None:
    config = Target.model_validate({"name": "files", "type": "unknown"})
    with pytest.raises(TargetError):
        TargetBase.factory(config)


def test_without_config_model_raises() -> None:
    config = Target.model_validate({"name": "files", "type": "file"})
    with pytest.raises(TargetError):
        TargetBase(config)
