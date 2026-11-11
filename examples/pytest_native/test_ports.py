"""Original examples for the maintained iniconfig and jdcal ports.

Add the repository's ports directory to PYTHONPATH/PYSTACHY_PATH when running.
"""

from iniconfig import IniConfig, ParseError
import jdcal
import pytest


@pytest.fixture
def configuration():
    return IniConfig("example.ini", data="[runner]\nname = native\nworkers = 2\n")


def test_configuration_values(configuration):
    assert configuration["runner"]["name"] == "native"
    assert configuration.get("runner", "workers", convert=int) == 2
    assert configuration.get("runner", "missing", default="fallback") == "fallback"


def test_duplicate_configuration_section():
    with pytest.raises(ParseError):
        IniConfig("example.ini", data="[runner]\n[runner]\n")


@pytest.mark.parametrize("year,month,day", [(1900, 3, 1), (2000, 2, 29), (2026, 11, 10)])
def test_calendar_round_trip(year: int, month: int, day: int):
    first, second = jdcal.gcal2jd(year, month, day)
    actual_year, actual_month, actual_day, fraction = jdcal.jd2gcal(first, second)
    assert (actual_year, actual_month, actual_day) == (year, month, day)
    assert fraction == 0.0
