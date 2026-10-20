# Adapted from CPython 3.13.16 Lib/test/datetimetester.py (which Lib/test/test_datetime.py
# runs), class TestTimeDelta: test_constructor, test_computations, test_disallowed_computations,
# test_basic_attributes, test_total_seconds, test_carries, test_hash_equality, test_compare,
# test_str, test_repr, test_resolution_info, test_overflow, test_microsecond_rounding,
# test_massive_normalization, test_bool, test_division, test_remainder and test_divmod; and class
# TestDate: test_basic_attributes, test_ordinal_conversions, test_extreme_ordinals,
# test_bad_constructor_arguments, test_hash_equality, test_computations, test_overflow,
# test_fromtimestamp_with_none_arg, test_weekday, test_iso_long_years, test_isoformat,
# test_ctime, test_strftime, test_format, test_resolution_info, test_extreme_timedelta,
# test_timetuple, test_compare, test_bool, test_replace, test_fromisoformat,
# test_fromisoformat_date_examples and test_fromisoformat_fails; commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# datetime is lib/datetime.py (CPython's _pydatetime with marked edits). Each test method becomes
# a function of the same name; TestDate's that TestTimeDelta also has end in _TestDate, and a
# method whose statements cannot share one function is split (NAME_2). self.theclass is the
# class tested (timedelta or date), and an alias of it (td = timedelta, cls = self.theclass) is
# the class's name; the methods' local classes are module classes. assertEqual(a, b) (and its
# aliases, eq = self.assertEqual) is eq(a, b), which prints a and asserts a == b; assertTrue(x)
# eq(bool(x), True); assertRaises(E, f, *args), assertRaisesRegex and `with
# self.assertRaises(E):` are try statements that print the exception. Of a method's other
# statements, a function keeps the ones that bind what its assertions read, in upstream's
# order. 223 of these methods' 334 assertions are adopted, all but these (datetimetester.py
# line numbers):
# EXCLUDED upstream cases:
# - reflected operators (rejected: "reflected operator methods are not supported (int *
#   timedelta calls timedelta.__rmul__)", also float *, date * and date + datetime): 562-614 of
#   test_computations (22 assertions), 876 877, 1309 1315; `//`, `*` of other operands
#   (compile-time TypeErrors here: "unsupported operand type(s) for //: 'int' and 'timedelta'",
#   ...): 639 1311-1313; timedelta results compared with ints or dates (rejected: "expected
#   timedelta, got int", "... got date"): 992 1009 1281 1283 1306
# - == < > of a date and an int or another class's object (rejected: "__eq__() of
#   datetime.date cannot compare an operand of type int"): test_mixed_compare 1679-1699; OTHERSTUFF
#   (a tuple of mixed types): 733 1661
# - hash values: equal dates hash alike, but the values differ from CPython's (documented,
#   lib/compatibility.md): 1247 1259, and the dict lookups after them that CPython's fail alone:
#   698 1252 1253 1264 1265
# - subclasses of date with __new__ (rejected: "the special method __new__ is not supported"):
#   test_subclass_date, test_subclass_alternate_constructors; a class method through an object
#   (rejected: "calling class method fromordinal() on an object of date, which may be one of
#   datetime, is not supported"): 1200 1202 1212 1214; DateSubclass.fromisoformat() 1932
# - date.__format__(123) (rejected at compile time: "__format__ must return str, and
#   datetime.date.__format__() returns None"; CPython raises TypeError when it runs): 1543;
#   date.strftime() with too few or many arguments or an int (compile-time errors here, worded
#   as for a Python function: "date.strftime() missing 1 required positional argument:
#   'format'", where CPython's C module says "strftime() missing required argument 'format'
#   (pos 1)"; "date.strftime() takes 2 positional arguments but 3 were given", CPython
#   "strftime() takes at most 1 argument (2 given)"; "expected str, got int"): 1487-1489
# - fromtimestamp() of local time (time.mktime(), rejected: "unsupported call time.mktime(...)";
#   NotImplementedError: datetime: local time is not supported, documented): 1338-1340 1347,
#   test_today (round() of a timedelta, rejected: "type timedelta doesn't define __round__
#   method") 1381
# - date.fromisocalendar() of 2<<32 components: lib/datetime raises "Year is out of range:
#   8589934592", "Invalid week: ...", "Invalid day: ...", where CPython's C module raises
#   "ISO calendar component out of range": 2022 (all of test_fromisocalendar_value_errors);
#   date(*a_list) and fromisocalendar(*isocalendar()) (rejected: "unpacking a list[int] into the
#   arguments of datetime.date() is not supported (a tuple's items are)"): 1724 1996
# - lists of mixed types or empty lists (rejected: "cannot iterate over tuple[int,float]",
#   "expected float, got int; this list literal needs list[int | float] ...", "cannot infer the
#   type of 'test_cases', an empty list so far"): 630 661 1299 1415 2045; ranges as values (1184
#   1273); date as a value (cls.resolution, rejected: "class 'datetime.date' cannot be used as a
#   value"): 1574 1575; 1150 (an int and a date in one list)
# - eval(repr()) (792 1135), copy, pickle, io, support, _time (time.strftime()),
#   test_backdoor_resistance (date() of a bytes pickle state, 1855 1858, rejected: "date.__init__()
#   missing 2 required positional arguments: 'month' and 'day'"), test_strftime_trailing_percent,
#   test_strftime_y2k,
#   test_pickling*, test_compat_unpickle, test_isocalendar_pickling, test_subclass_replace,
#   test_fromisoformat_fails_typeerror (a list of bytes, None and io.StringIO; fromisoformat(b'...')
#   is rejected: "expected str, got bytes"), test_insane_fromtimestamp
# - the other TestDate methods (test_today, test_fromtimestamp, test_insane_*,
#   test_isocalendar, test_fromisocalendar*, test_mixed_compare, test_subclass_*): as above;
#   test_harmless_mixed_comparison and test_harmful_mixed_comparison (HarmlessMixedComparison:
#   comparisons with () and ALWAYS_EQ), TestDateOnly, and the classes of datetime, time,
#   timezone and tzinfo, which tests/programs/library/lib_datetime_*.py check
import sys
from operator import truediv, floordiv, mod
from datetime import MINYEAR, MAXYEAR
from datetime import timedelta
from datetime import tzinfo
from datetime import time
from datetime import timezone
from datetime import date, datetime


def eq(got, expected) -> None:
    print(repr(got))
    assert got == expected, (got, expected)


def test_constructor() -> None:
    eq(timedelta(), timedelta(weeks=0, days=0, hours=0, minutes=0, seconds=0,
                    milliseconds=0, microseconds=0))
    eq(timedelta(1), timedelta(days=1))
    eq(timedelta(0, 1), timedelta(seconds=1))
    eq(timedelta(0, 0, 1), timedelta(microseconds=1))
    eq(timedelta(weeks=1), timedelta(days=7))
    eq(timedelta(days=1), timedelta(hours=24))
    eq(timedelta(hours=1), timedelta(minutes=60))
    eq(timedelta(minutes=1), timedelta(seconds=60))
    eq(timedelta(seconds=1), timedelta(milliseconds=1000))
    eq(timedelta(milliseconds=1), timedelta(microseconds=1000))
    eq(timedelta(weeks=1.0/7), timedelta(days=1))
    eq(timedelta(days=1.0/24), timedelta(hours=1))
    eq(timedelta(hours=1.0/60), timedelta(minutes=1))
    eq(timedelta(minutes=1.0/60), timedelta(seconds=1))
    eq(timedelta(seconds=0.001), timedelta(milliseconds=1))
    eq(timedelta(milliseconds=0.001), timedelta(microseconds=1))


def test_computations() -> None:
    a = timedelta(7) # One week
    b = timedelta(0, 60) # One minute
    c = timedelta(0, 0, 1000) # One millisecond
    eq(a+b+c, timedelta(7, 60, 1000))
    eq(a-b, timedelta(6, 24*3600 - 60))
    eq(b.__rsub__(a), timedelta(6, 24*3600 - 60))
    eq(-a, timedelta(-7))
    eq(+a, timedelta(7))
    eq(-b, timedelta(-1, 24*3600 - 60))
    eq(-c, timedelta(-1, 24*3600 - 1, 999000))
    eq(abs(a), a)
    eq(abs(-a), a)
    eq(timedelta(6, 24*3600), a)
    eq(timedelta(0, 0, 60*1000000), b)
    eq(a*10, timedelta(70))
    eq(b*10, timedelta(0, 600))
    eq(b*10, timedelta(0, 600))
    eq(c*10, timedelta(0, 0, 10000))
    eq(c*10, timedelta(0, 0, 10000))
    eq(a*-1, -a)
    eq(b*-2, -b-b)
    eq(c*-2, -c+-c)
    eq(b*(60*24), (b*60)*24)
    eq(c*1000, timedelta(0, 1))
    eq(a//7, timedelta(1))
    eq(b//10, timedelta(0, 6))
    eq(c//1000, timedelta(0, 0, 1))
    eq(a//10, timedelta(0, 7*24*360))
    eq(a//3600000, timedelta(0, 0, 7*24*1000))
    eq(a/0.5, timedelta(14))
    eq(b/0.5, timedelta(0, 120))
    eq(a/7, timedelta(1))
    eq(b/10, timedelta(0, 6))
    eq(c/1000, timedelta(0, 0, 1))
    eq(a/10, timedelta(0, 7*24*360))
    eq(a/3600000, timedelta(0, 0, 7*24*1000))
    eq(timedelta(seconds=1) * 0.123456, timedelta(microseconds=123456))
    eq(timedelta(seconds=1) * 0.6112295, timedelta(microseconds=611229))
    eq(timedelta(seconds=1) / (1 / 0.6112295), timedelta(microseconds=611229))
    eq(timedelta(999999999, 86399, 999999) - timedelta(999999999, 86399, 999998), timedelta(0, 0, 1))
    eq(timedelta(999999999, 1, 1) - timedelta(999999999, 1, 0), timedelta(0, 0, 1))


def test_disallowed_computations() -> None:
    a = timedelta(42)
    zero = 0
    try:
        (lambda: a // zero)()
    except ZeroDivisionError as e:
        print(type(e).__name__ + ':', e)
    try:
        (lambda: a / zero)()
    except ZeroDivisionError as e:
        print(type(e).__name__ + ':', e)
    try:
        (lambda: a / 0.0)()
    except ZeroDivisionError as e:
        print(type(e).__name__ + ':', e)
    try:
        (lambda: a / '')()
    except TypeError as e:
        print(type(e).__name__ + ':', e)


def test_basic_attributes() -> None:
    days, seconds, us = 1, 7, 31
    td = timedelta(days, seconds, us)
    eq(td.days, days)
    eq(td.seconds, seconds)
    eq(td.microseconds, us)


def test_total_seconds() -> None:
    td = timedelta(days=365)
    eq(td.total_seconds(), 31536000.0)
    for ms in [-1, -2, -123]:
        td = timedelta(microseconds=ms)
        eq(td.total_seconds(), td / timedelta(seconds=1))


def test_carries() -> None:
    t1 = timedelta(days=100,
                   weeks=-7,
                   hours=-24*(100-49),
                   minutes=-3,
                   seconds=12,
                   microseconds=(3*60 - 12) * 1e6 + 1)
    t2 = timedelta(microseconds=1)
    eq(t1, t2)


def test_hash_equality() -> None:
    t1 = timedelta(days=100,
                   weeks=-7,
                   hours=-24*(100-49),
                   minutes=-3,
                   seconds=12,
                   microseconds=(3*60 - 12) * 1000000)
    t2 = timedelta()
    eq(hash(t1), hash(t2))
    t1 += timedelta(weeks=7)
    t2 += timedelta(days=7*7)
    eq(t1, t2)
    eq(hash(t1), hash(t2))
    d = {t1: 1}
    eq(len(d), 1)


def test_compare() -> None:
    t1 = timedelta(2, 3, 4)
    t2 = timedelta(2, 3, 4)
    eq(t1, t2)
    eq(bool(t1 <= t2), True)
    eq(bool(t1 >= t2), True)
    eq(bool(t1 != t2), False)
    eq(bool(t1 < t2), False)
    eq(bool(t1 > t2), False)
    for args in (3, 3, 3), (2, 4, 4), (2, 3, 5):
        t2 = timedelta(*args)   # this is larger than t1
        eq(bool(t1 < t2), True)
        eq(bool(t2 > t1), True)
        eq(bool(t1 <= t2), True)
        eq(bool(t2 >= t1), True)
        eq(bool(t1 != t2), True)
        eq(bool(t2 != t1), True)
        eq(bool(t1 == t2), False)
        eq(bool(t2 == t1), False)
        eq(bool(t1 > t2), False)
        eq(bool(t2 < t1), False)
        eq(bool(t1 >= t2), False)
        eq(bool(t2 <= t1), False)


def test_str() -> None:
    eq(str(timedelta(1)), "1 day, 0:00:00")
    eq(str(timedelta(-1)), "-1 day, 0:00:00")
    eq(str(timedelta(2)), "2 days, 0:00:00")
    eq(str(timedelta(-2)), "-2 days, 0:00:00")
    eq(str(timedelta(hours=12, minutes=58, seconds=59)), "12:58:59")
    eq(str(timedelta(hours=2, minutes=3, seconds=4)), "2:03:04")
    eq(str(timedelta(weeks=-30, hours=23, minutes=12, seconds=34)), "-210 days, 23:12:34")
    eq(str(timedelta(milliseconds=1)), "0:00:00.001000")
    eq(str(timedelta(microseconds=3)), "0:00:00.000003")
    eq(str(timedelta(days=999999999, hours=23, minutes=59, seconds=59,
                   microseconds=999999)), "999999999 days, 23:59:59.999999")
    eq(f'-({-timedelta(hours=-1)!s})', "-(1:00:00)")


def test_repr() -> None:
    name = 'datetime.' + timedelta.__name__
    eq(repr(timedelta(1)), "%s(days=1)" % name)
    eq(repr(timedelta(10, 2)), "%s(days=10, seconds=2)" % name)
    eq(repr(timedelta(-10, 2, 400000)), "%s(days=-10, seconds=2, microseconds=400000)" % name)
    eq(repr(timedelta(seconds=60)), "%s(seconds=60)" % name)
    eq(repr(timedelta()), "%s(0)" % name)
    eq(repr(timedelta(microseconds=100)), "%s(microseconds=100)" % name)
    eq(repr(timedelta(days=1, microseconds=100)), "%s(days=1, microseconds=100)" % name)
    eq(repr(timedelta(seconds=1, microseconds=100)), "%s(seconds=1, microseconds=100)" % name)


def test_resolution_info() -> None:
    eq(isinstance(timedelta.min, timedelta), True)
    eq(isinstance(timedelta.max, timedelta), True)
    eq(isinstance(timedelta.resolution, timedelta), True)
    eq(bool(timedelta.max > timedelta.min), True)
    eq(timedelta.min, timedelta(-999999999))
    eq(timedelta.max, timedelta(999999999, 24*3600-1, 1e6-1))
    eq(timedelta.resolution, timedelta(0, 0, 1))


def test_overflow() -> None:
    tiny = timedelta.resolution
    td = timedelta.min + tiny
    td -= tiny  # no problem
    try:
        td.__sub__(tiny)
    except OverflowError as e:
        print(type(e).__name__ + ':', e)
    try:
        td.__add__(-tiny)
    except OverflowError as e:
        print(type(e).__name__ + ':', e)
    td = timedelta.max - tiny
    td += tiny  # no problem
    try:
        td.__add__(tiny)
    except OverflowError as e:
        print(type(e).__name__ + ':', e)
    try:
        td.__sub__(-tiny)
    except OverflowError as e:
        print(type(e).__name__ + ':', e)
    try:
        (lambda: -timedelta.max)()
    except OverflowError as e:
        print(type(e).__name__ + ':', e)
    day = timedelta(1)
    try:
        day.__mul__(10**9)
    except OverflowError as e:
        print(type(e).__name__ + ':', e)
    try:
        day.__mul__(1e9)
    except OverflowError as e:
        print(type(e).__name__ + ':', e)
    try:
        day.__truediv__(1e-20)
    except OverflowError as e:
        print(type(e).__name__ + ':', e)
    try:
        day.__truediv__(1e-10)
    except OverflowError as e:
        print(type(e).__name__ + ':', e)
    try:
        day.__truediv__(9e-10)
    except OverflowError as e:
        print(type(e).__name__ + ':', e)


def test_microsecond_rounding() -> None:
    eq(timedelta(milliseconds=0.4/1000), timedelta(0))
    eq(timedelta(milliseconds=-0.4/1000), timedelta(0))
    eq(timedelta(milliseconds=0.5/1000), timedelta(microseconds=0))
    eq(timedelta(milliseconds=-0.5/1000), timedelta(microseconds=-0))
    eq(timedelta(milliseconds=0.6/1000), timedelta(microseconds=1))
    eq(timedelta(milliseconds=-0.6/1000), timedelta(microseconds=-1))
    eq(timedelta(milliseconds=1.5/1000), timedelta(microseconds=2))
    eq(timedelta(milliseconds=-1.5/1000), timedelta(microseconds=-2))
    eq(timedelta(seconds=0.5/10**6), timedelta(microseconds=0))
    eq(timedelta(seconds=-0.5/10**6), timedelta(microseconds=-0))
    eq(timedelta(seconds=1/2**7), timedelta(microseconds=7812))
    eq(timedelta(seconds=-1/2**7), timedelta(microseconds=-7812))
    us_per_hour = 3600e6
    us_per_day = us_per_hour * 24
    eq(timedelta(days=.4/us_per_day), timedelta(0))
    eq(timedelta(hours=.2/us_per_hour), timedelta(0))
    eq(timedelta(days=.4/us_per_day, hours=.2/us_per_hour), timedelta(microseconds=1))
    eq(timedelta(days=-.4/us_per_day), timedelta(0))
    eq(timedelta(hours=-.2/us_per_hour), timedelta(0))
    eq(timedelta(days=-.4/us_per_day, hours=-.2/us_per_hour), timedelta(microseconds=-1))


def test_massive_normalization() -> None:
    td = timedelta(microseconds=-1)
    eq((td.days, td.seconds, td.microseconds), (-1, 24*3600-1, 999999))


def test_bool() -> None:
    eq(bool(timedelta(1)), True)
    eq(bool(timedelta(0, 1)), True)
    eq(bool(timedelta(0, 0, 1)), True)
    eq(bool(timedelta(microseconds=1)), True)
    eq(bool(timedelta(0)), False)


def test_division() -> None:
    t = timedelta(hours=1, minutes=24, seconds=19)
    second = timedelta(seconds=1)
    eq(t / second, 5059.0)
    eq(t // second, 5059)
    t = timedelta(minutes=2, seconds=30)
    minute = timedelta(minutes=1)
    eq(t / minute, 2.5)
    eq(t // minute, 2)
    zerotd = timedelta(0)
    try:
        truediv(t, zerotd)
    except ZeroDivisionError as e:
        print(type(e).__name__ + ':', e)
    try:
        floordiv(t, zerotd)
    except ZeroDivisionError as e:
        print(type(e).__name__ + ':', e)


def test_remainder() -> None:
    t = timedelta(minutes=2, seconds=30)
    minute = timedelta(minutes=1)
    r = t % minute
    eq(r, timedelta(seconds=30))
    t = timedelta(minutes=-2, seconds=30)
    r = t %  minute
    eq(r, timedelta(seconds=30))
    zerotd = timedelta(0)
    try:
        mod(t, zerotd)
    except ZeroDivisionError as e:
        print(type(e).__name__ + ':', e)


def test_divmod() -> None:
    t = timedelta(minutes=2, seconds=30)
    minute = timedelta(minutes=1)
    q, r = divmod(t, minute)
    eq(q, 2)
    eq(r, timedelta(seconds=30))
    t = timedelta(minutes=-2, seconds=30)
    q, r = divmod(t, minute)
    eq(q, -2)
    eq(r, timedelta(seconds=30))
    zerotd = timedelta(0)
    try:
        divmod(t, zerotd)
    except ZeroDivisionError as e:
        print(type(e).__name__ + ':', e)


def test_basic_attributes_TestDate() -> None:
    dt = date(2002, 3, 1)
    eq(dt.year, 2002)
    eq(dt.month, 3)
    eq(dt.day, 1)


def test_ordinal_conversions() -> None:
    for year in range(MINYEAR, MAXYEAR+1, 7):
        # Verify (year, 1, 1) -> ordinal -> y, m, d is identity.
        d = date(year, 1, 1)
        n = d.toordinal()
        d2 = date.fromordinal(n)
        eq(d, d2)
        if year > 1:
            d = date.fromordinal(n-1)
            d2 = date(year-1, 12, 31)
            eq(d, d2)
            eq(d2.toordinal(), n-1)


def test_extreme_ordinals() -> None:
    a = date.min
    a = date(a.year, a.month, a.day)  # get rid of time parts
    aord = a.toordinal()
    b = a + timedelta(days=1)
    eq(b.toordinal(), aord + 1)
    eq(b, date.fromordinal(aord + 1))
    a = date.max
    a = date(a.year, a.month, a.day)  # get rid of time parts
    aord = a.toordinal()
    b = a - timedelta(days=1)
    eq(b.toordinal(), aord - 1)
    eq(b, date.fromordinal(aord - 1))


def test_bad_constructor_arguments() -> None:
    try:
        date(MINYEAR-1, 1, 1)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        date(MAXYEAR+1, 1, 1)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        date(2000, 0, 1)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        date(2000, 13, 1)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        date(2000, 2, 30)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        date(2001, 2, 29)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        date(2100, 2, 29)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        date(1900, 2, 29)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        date(2000, 1, 0)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        date(2000, 1, 32)
    except ValueError as e:
        print(type(e).__name__ + ':', e)


def test_hash_equality_TestDate() -> None:
    d = date(2000, 12, 31)
    e = date(2000, 12, 31)
    eq(d, e)
    dic = {d: 1}
    eq(len(dic), 1)


def test_hash_equality_TestDate_2() -> None:
    d = date(2001,  1,  1)
    e = date(2001,  1,  1)
    eq(d, e)
    dic = {d: 1}
    eq(len(dic), 1)


def test_computations_TestDate() -> None:
    a = date(2002, 1, 31)
    b = date(1956, 1, 31)
    c = date(2001,2,1)
    diff = a-b
    eq(diff.seconds, 0)
    eq(diff.microseconds, 0)
    day = timedelta(1)
    week = timedelta(7)
    a = date(2002, 3, 2)
    eq(a + day, date(2002, 3, 3))
    eq(a - day, date(2002, 3, 1))
    eq(a + week, date(2002, 3, 9))
    eq(a - week, date(2002, 2, 23))
    eq((a + week) - a, week)
    eq((a + day) - a, day)
    eq((a - week) - a, -week)
    eq((a - day) - a, -day)
    eq(a - (a + week), -week)
    eq(a - (a + day), -day)
    eq(a - (a - week), week)
    eq(a - (a - day), day)
    eq(c - (c - day), day)
    try:
        (lambda: day * a)()
    except TypeError as e:
        print(type(e).__name__ + ':', e)
    try:
        (lambda: day // a)()
    except TypeError as e:
        print(type(e).__name__ + ':', e)


def test_overflow_TestDate() -> None:
    tiny = date.resolution
    for delta in [tiny, timedelta(1), timedelta(2)]:
        dt = date.min + delta
        dt -= delta  # no problem
        try:
            dt.__sub__(delta)
        except OverflowError as e:
            print(type(e).__name__ + ':', e)
        try:
            dt.__add__(-delta)
        except OverflowError as e:
            print(type(e).__name__ + ':', e)
        dt = date.max - delta
        dt += delta  # no problem
        try:
            dt.__add__(delta)
        except OverflowError as e:
            print(type(e).__name__ + ':', e)
        try:
            dt.__sub__(-delta)
        except OverflowError as e:
            print(type(e).__name__ + ':', e)


def test_fromtimestamp_with_none_arg() -> None:
    try:
        date.fromtimestamp(None)
    except TypeError as e:
        print(type(e).__name__ + ':', e)


def test_weekday() -> None:
    for i in range(7):
        # March 4, 2002 is a Monday
        eq(date(2002, 3, 4+i).weekday(), i)
        eq(date(2002, 3, 4+i).isoweekday(), i+1)
        eq(date(1956, 1, 2+i).weekday(), i)
        eq(date(1956, 1, 2+i).isoweekday(), i+1)


def test_iso_long_years() -> None:
    ISO_LONG_YEARS_TABLE = """
          4   32   60   88
          9   37   65   93
         15   43   71   99
         20   48   76
         26   54   82

        105  133  161  189
        111  139  167  195
        116  144  172
        122  150  178
        128  156  184

        201  229  257  285
        207  235  263  291
        212  240  268  296
        218  246  274
        224  252  280

        303  331  359  387
        308  336  364  392
        314  342  370  398
        320  348  376
        325  353  381
    """
    iso_long_years = sorted(map(int, ISO_LONG_YEARS_TABLE.split()))
    L = []
    for i in range(400):
        d = date(2000+i, 12, 31)
        d1 = date(1600+i, 12, 31)
        eq(d.isocalendar()[1:], d1.isocalendar()[1:])
        if d.isocalendar()[1] == 53:
            L.append(i)
    eq(L, iso_long_years)


def test_isoformat() -> None:
    t = date(2, 3, 2)
    eq(t.isoformat(), "0002-03-02")


def test_ctime() -> None:
    t = date(2002, 3, 2)
    eq(t.ctime(), "Sat Mar  2 00:00:00 2002")


def test_strftime() -> None:
    t = date(2005, 3, 2)
    eq(t.strftime("m:%m d:%d y:%y"), "m:03 d:02 y:05")
    eq(t.strftime(""), "")
    eq(t.strftime('x'*1000), 'x'*1000)
    eq(t.strftime("%m"), "03")
    eq(t.strftime("'%z' '%:z' '%Z'"), "'' '' ''")


class A(date):
    def __str__(self):
        return 'A'


class B(date):
    def strftime(self, format_spec):
        return 'B'


def test_format() -> None:
    dt = date(2007, 9, 10)
    eq(dt.__format__(''), str(dt))
    a = A(2007, 9, 10)
    eq(a.__format__(''), 'A')
    b = B(2007, 9, 10)
    eq(b.__format__(''), str(dt))
    for fmt in ["m:%m d:%d y:%y",
                "m:%m d:%d y:%y H:%H M:%M S:%S",
                "%z %:z %Z",
                ]:
        eq(dt.__format__(fmt), dt.strftime(fmt))
        eq(a.__format__(fmt), dt.strftime(fmt))
        eq(b.__format__(fmt), 'B')


def test_resolution_info_TestDate() -> None:
    eq(isinstance(date.resolution, timedelta), True)
    eq(bool(date.max > date.min), True)


def test_extreme_timedelta() -> None:
    big = date.max - date.min
    n = (big.days*24*3600 + big.seconds)*1000000 + big.microseconds
    justasbig = timedelta(0, 0, n)
    eq(big, justasbig)
    eq(date.min + big, date.max)
    eq(date.max - big, date.min)


def test_timetuple() -> None:
    for i in range(7):
        # January 2, 1956 is a Monday (0)
        d = date(1956, 1, 2+i)
        t = d.timetuple()
        eq(t, (1956, 1, 2+i, 0, 0, 0, i, 2+i, -1))
        d = date(1956, 2, 1+i)
        t = d.timetuple()
        eq(t, (1956, 2, 1+i, 0, 0, 0, (2+i)%7, 32+i, -1))
        d = date(1956, 3, 1+i)
        t = d.timetuple()
        eq(t, (1956, 3, 1+i, 0, 0, 0, (3+i)%7, 61+i, -1))
        eq(t.tm_year, 1956)
        eq(t.tm_mon, 3)
        eq(t.tm_mday, 1+i)
        eq(t.tm_hour, 0)
        eq(t.tm_min, 0)
        eq(t.tm_sec, 0)
        eq(t.tm_wday, (3+i)%7)
        eq(t.tm_yday, 61+i)
        eq(t.tm_isdst, -1)


def test_compare_TestDate() -> None:
    t1 = date(2, 3, 4)
    t2 = date(2, 3, 4)
    eq(t1, t2)
    eq(bool(t1 <= t2), True)
    eq(bool(t1 >= t2), True)
    eq(bool(t1 != t2), False)
    eq(bool(t1 < t2), False)
    eq(bool(t1 > t2), False)
    for args in (3, 3, 3), (2, 4, 4), (2, 3, 5):
        t2 = date(*args)   # this is larger than t1
        eq(bool(t1 < t2), True)
        eq(bool(t2 > t1), True)
        eq(bool(t1 <= t2), True)
        eq(bool(t2 >= t1), True)
        eq(bool(t1 != t2), True)
        eq(bool(t2 != t1), True)
        eq(bool(t1 == t2), False)
        eq(bool(t2 == t1), False)
        eq(bool(t1 > t2), False)
        eq(bool(t2 < t1), False)
        eq(bool(t1 >= t2), False)
        eq(bool(t2 <= t1), False)


def test_bool_TestDate() -> None:
    eq(bool(date.min), True)
    eq(bool(date.max), True)


def test_replace() -> None:
    base = date(2000, 2, 29)
    try:
        base.replace(year=2001)
    except ValueError as e:
        print(type(e).__name__ + ':', e)


def test_fromisoformat() -> None:
    base_dates = [
        (1, 1, 1),
        (1000, 2, 14),
        (1900, 1, 1),
        (2000, 2, 29),
        (2004, 11, 12),
        (2004, 4, 3),
        (2017, 5, 30)
    ]
    for dt_tuple in base_dates:
        dt = date(*dt_tuple)
        dt_str = dt.isoformat()
        dt_rt = date.fromisoformat(dt.isoformat())
        eq(dt, dt_rt)


def test_fromisoformat_date_examples() -> None:
    examples = [
        ('00010101', date(1, 1, 1)),
        ('20000101', date(2000, 1, 1)),
        ('20250102', date(2025, 1, 2)),
        ('99991231', date(9999, 12, 31)),
        ('0001-01-01', date(1, 1, 1)),
        ('2000-01-01', date(2000, 1, 1)),
        ('2025-01-02', date(2025, 1, 2)),
        ('9999-12-31', date(9999, 12, 31)),
        ('2025W01', date(2024, 12, 30)),
        ('2025-W01', date(2024, 12, 30)),
        ('2025W014', date(2025, 1, 2)),
        ('2025-W01-4', date(2025, 1, 2)),
        ('2026W01', date(2025, 12, 29)),
        ('2026-W01', date(2025, 12, 29)),
        ('2026W013', date(2025, 12, 31)),
        ('2026-W01-3', date(2025, 12, 31)),
        ('2022W52', date(2022, 12, 26)),
        ('2022-W52', date(2022, 12, 26)),
        ('2022W527', date(2023, 1, 1)),
        ('2022-W52-7', date(2023, 1, 1)),
        ('2015W534', date(2015, 12, 31)),      # Has week 53
        ('2015-W53-4', date(2015, 12, 31)),    # Has week 53
        ('2015-W53-5', date(2016, 1, 1)),
        ('2020W531', date(2020, 12, 28)),      # Leap year
        ('2020-W53-1', date(2020, 12, 28)),    # Leap year
        ('2020-W53-6', date(2021, 1, 2)),
    ]
    for input_str, expected in examples:
        actual = date.fromisoformat(input_str)
        eq(actual, expected)


def test_fromisoformat_fails() -> None:
    bad_strs = [
        '',                 # Empty string
        '\ud800',           # bpo-34454: Surrogate code point
        '009-03-04',        # Not 10 characters
        '123456789',        # Not a date
        '200a-12-04',       # Invalid character in year
        '2009-1a-04',       # Invalid character in month
        '2009-12-0a',       # Invalid character in day
        '2009-01-32',       # Invalid day
        '2009-02-29',       # Invalid leap day
        '2019-W53-1',       # No week 53 in 2019
        '2020-W54-1',       # No week 54
        '0000-W25-1',       # Invalid year
        '10000-W25-1',      # Invalid year
        '2020-W25-0',       # Invalid day-of-week
        '2020-W25-8',       # Invalid day-of-week
        # gh-152204: each fixed-width field must be exactly N ASCII digits
        '2020+12',          # '+' in a basic-format field
        '2020 12',          # space in a basic-format field
        '+020-06-15',       # leading sign in the year
        '202012+9',         # '+' in the day field
        '2020-W 5',         # space in the week number
        '2020061',          # 7 chars: day slice reads a 1-character tail
        '2020-W2',          # 1-digit week number
        '٢025-03-09',       # Unicode characters
        '2009\ud80002\ud80028',     # Separators are surrogate codepoints
    ]
    for bad_str in bad_strs:
        try:
            date.fromisoformat(bad_str)
        except ValueError as e:
            print(type(e).__name__ + ':', e)


test_constructor()
test_computations()
test_disallowed_computations()
test_basic_attributes()
test_total_seconds()
test_carries()
test_hash_equality()
test_compare()
test_str()
test_repr()
test_resolution_info()
test_overflow()
test_microsecond_rounding()
test_massive_normalization()
test_bool()
test_division()
test_remainder()
test_divmod()
test_basic_attributes_TestDate()
test_ordinal_conversions()
test_extreme_ordinals()
test_bad_constructor_arguments()
test_hash_equality_TestDate()
test_hash_equality_TestDate_2()
test_computations_TestDate()
test_overflow_TestDate()
test_fromtimestamp_with_none_arg()
test_weekday()
test_iso_long_years()
test_isoformat()
test_ctime()
test_strftime()
test_format()
test_resolution_info_TestDate()
test_extreme_timedelta()
test_timetuple()
test_compare_TestDate()
test_bool_TestDate()
test_replace()
test_fromisoformat()
test_fromisoformat_date_examples()
test_fromisoformat_fails()
