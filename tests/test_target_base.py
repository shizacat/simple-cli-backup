from pathlib import Path

import pytest
from pydantic import BaseModel

from sback.lib.config import Target
from sback.lib.exception import TargetError
from sback.lib.target_base import TargetBase


def test_factory_unknown_type() -> None:
    class _Nameless(TargetBase):
        pass

    config = Target.model_validate({"name": "files", "type": "unknown"})
    with pytest.raises(TargetError, match="not found"):
        TargetBase.factory(config)


def test_process_is_not_implemented(tmp_path: Path) -> None:
    class _Empty(BaseModel):
        pass

    class _Bare(TargetBase[_Empty]):
        name = "bare-target"
        description = "bare"
        config_model = _Empty

    target = _Bare(
        Target.model_validate({"name": "files", "type": "bare-target", "config": {}})
    )
    with pytest.raises(NotImplementedError):
        target.process(tmp_path)


def test_without_config_model_raises() -> None:
    config = Target.model_validate({"name": "files", "type": "file"})
    with pytest.raises(TargetError):
        TargetBase(config)
