from sback.lib.exception import TargetError
from sback.lib.notification import Notification, Status


def test_body_uses_each_item_status() -> None:
    report = Notification("daily")
    report.add_target("files", Status.GOOD)
    report.add_target("db", Status.BAD, "down")
    report.add_place("local", Status.GOOD)

    text = report.body()

    assert report.status is Status.BAD
    assert text.startswith("daily - Error\nThe target:\n")
    assert "    * files - Success. \n" in text
    assert "    * db - Error. down\n" in text
    assert "Backup Locations:\n    * local - Success. \n" in text


def test_status_stays_good_without_failures() -> None:
    report = Notification("daily")
    report.add_target("files", Status.GOOD, "ok")

    assert report.status is Status.GOOD
    assert report.body().startswith("daily - Success\n")


def test_fail_keeps_the_first_error() -> None:
    report = Notification("daily")
    report.fail(TargetError("one"))
    report.fail(TargetError("two"))

    assert isinstance(report.error, TargetError)
    assert str(report.error) == "one"
