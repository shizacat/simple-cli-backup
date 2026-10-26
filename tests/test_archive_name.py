import pytest

from sback.lib.archive_name import _parts, archiv_name_add_index, is_archive_name
from sback.lib.exception import ArchiveNameError


def test_first_copy_gets_zero_index() -> None:
    assert (
        archiv_name_add_index("daily_2026.10.26.tar", []) == "daily_2026.10.26.0000.tar"
    )


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


def test_names_outside_the_pattern_are_ignored() -> None:
    result = archiv_name_add_index(
        "daily_2026.10.26.tar",
        ["notes.txt", "other_2026.10.26.0004.tar", "daily_2026.10.26.0001.tar"],
    )
    assert result == "daily_2026.10.26.0002.tar"


def test_parts_rejects_a_name_without_index() -> None:
    with pytest.raises(ArchiveNameError):
        _parts("daily_2026.10.26.tar")


def test_name_with_index_is_rejected() -> None:
    assert is_archive_name("daily_2026.10.26.tar") is False
    with pytest.raises(ArchiveNameError):
        archiv_name_add_index("daily_2026.10.26.0000.tar", [])
