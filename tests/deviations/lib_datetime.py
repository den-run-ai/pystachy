# Documented deviations of lib/datetime (CPython 3.13's _pydatetime with marked edits that follow
# _datetimemodule.c) from CPython.
from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import Callable


def show(label: str, f: Callable[[], str]) -> None:
    try:
        print(label, f())
    except (ValueError, OverflowError, TypeError, NotImplementedError) as e:
        print(label, type(e).__name__ + ":", e)


# Pystachy's time module has no localtime() or mktime(): operations in the local time zone
# raise NotImplementedError when they run. CPython prints the local date and times.
show("today", lambda: str(date.today()))
show("now", lambda: str(datetime.now()))
show("fromtimestamp", lambda: str(datetime.fromtimestamp(0)))
show("timestamp", lambda: str(datetime(2024, 1, 1).timestamp()))
show("astimezone()", lambda: str(datetime(2024, 1, 1, tzinfo=UTC).astimezone()))
show("naive astimezone", lambda: str(datetime(2024, 1, 1).astimezone(UTC)))
show("%s", lambda: date(2024, 1, 1).strftime("%s"))

# Integers are 64-bit: operations through a timedelta's microseconds raise OverflowError beyond
# about 106751991 days, and so does a float count of microseconds of 2**63 or more. CPython
# prints 86399999999999.999 999999999 datetime.timedelta(days=499999999, seconds=86399,
# microseconds=999999) and datetime.timedelta(days=115740740, seconds=64000).
show("total_seconds", lambda: str(timedelta.max.total_seconds()))
show("//", lambda: str(timedelta.max // timedelta(1)))
show("/", lambda: repr(timedelta.max / 2))
show("float us", lambda: repr(timedelta(microseconds=1e19)))

# timezone(timedelta(0)) is a new object equal to timezone.utc (CPython returns timezone.utc
# itself: True), and a name of None is taken as omitted (CPython raises TypeError: timezone()
# argument 2 must be str, not None).
print(timezone(timedelta(0)) is timezone.utc, timezone(timedelta(0)) == timezone.utc,
      repr(timezone(timedelta(0))))
show("name None", lambda: repr(timezone(timedelta(hours=1), None)))

# Ordering a date and a datetime calls the datetime's reflected method first, as CPython does,
# but cannot return NotImplemented to it: the TypeError names that reflected comparison
# (CPython: '<' not supported between instances of 'datetime.date' and 'datetime.datetime').
show("date < datetime", lambda: str(date(2024, 1, 1) < datetime(2024, 1, 1)))

# A subclass of date: objects have no __class__, so repr() names date, and the results of
# arithmetic and replace() are dates (CPython: MyDate(2024, 2, 29) True True).
class MyDate(date):
    pass


md = MyDate(2024, 2, 29)
print(repr(md), isinstance(md + timedelta(0), MyDate), isinstance(md.replace(day=1), MyDate))

# The Python fallback uses None for omitted numeric replacement fields, and True
# for an omitted time zone. Explicit sentinel values preserve the original field;
# CPython's C methods raise TypeError. Explicit tzinfo=None still makes a naive value.
d = date(2024, 2, 29)
t = time(12, 34, 56, 789, tzinfo=UTC, fold=1)
dt = datetime(2024, 2, 29, 12, 34, 56, 789, tzinfo=UTC, fold=1)
print(repr(d.replace(year=None, month=None, day=None)))
print(repr(t.replace(hour=None, minute=None, second=None, microsecond=None, fold=None)))
print(repr(dt.replace(year=None, month=None, day=None, hour=None, minute=None,
                      second=None, microsecond=None, fold=None)))
print(repr(t.replace(tzinfo=True)), repr(dt.replace(tzinfo=True)))
print(repr(datetime.combine(d, t, tzinfo=True)))
print(t.replace(tzinfo=None).tzinfo is None, dt.replace(tzinfo=None).tzinfo is None,
      datetime.combine(d, t, tzinfo=None).tzinfo is None)
