import pytest

from sback.lib.archive_name import is_archive_name, archiv_name_add_index
from sback.lib.exception import ArchiveNameError


def test_first_copy_gets_zero_index() -> None:
    assert archiv_name_add_index("daily_2026.10.26.tar", []) == "daily_2026.10.26.0000.tar"


def test_next_index_follows_highest() -> None:
    result = archiv_name_add_index(
        "daily_2026.10.26.tar",
        ["daily_2026.10.26.0000.tar", "daily_2026.10.26.0002.tar"],
    )
    assert result == "daily_2026.10.26.0003.tar"


def test_extension_is_taken_from_the_name() -> None:
    assert (
        archiv_name_add_index("daily_2026.10.26.tar.gz", ["daily_2026.10.26.0000.tar"])
        == "daily_2026.10.26.0000.tar.gz"
    )


def test_name_with_index_is_rejected() -> None:
    assert is_archive_name("daily_2026.10.26.tar") is False
    with pytest.raises(ArchiveNameError):
        archiv_name_add_index("daily_2026.10.26.0000.tar", [])
