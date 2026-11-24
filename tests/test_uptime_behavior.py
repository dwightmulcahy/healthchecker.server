"""Uptime formatting boundary tests."""

from datetime import datetime, timedelta

from uptime import UpTime


def test_elapsed_time_and_display():
    timer = UpTime()
    timer.startDatetime = datetime.now() - timedelta(seconds=65)
    assert timer.current() >= 65
    assert "minute" in str(timer)
    assert repr(timer) == str(timer)


def test_empty_and_all_duration_units():
    timer = UpTime()
    assert timer.timetostring(0) == ""
    assert timer.timetostring(1) == "1 second"
    assert timer.timetostring(61) == "1 minute, 1 second"
    assert timer.timetostring(3600) == "1 hour"
    assert timer.timetostring(2 * 86400) == "2 days"
    assert timer.timetostring(2 * 365 * 86400) == "2 years"
    assert "month" in timer.timetostring(30 * 86400)
    assert "seconds" in timer.timetostring(2)
