# pystachy: numeric-values
# Pystachy port: the comment above, as CPython runs _datetime, whose objects hold their fields
# as machine values (docs/dynamic-any.md#numeric-value-modules)
"""Concrete date/time and related types.

See http://www.iana.org/time-zones/repository/tz-link.html for
time zone and DST data sources.
"""

# Pystachy port: CPython's datetime.py imports _datetime, its C accelerator, else this module,
# _pydatetime.py, whose code this file is. CPython runs _datetime, so where _pydatetime's
# observable behavior differs (messages, float arithmetic, comparisons), this port follows
# Modules/_datetimemodule.c. See lib/compatibility.md for the supported surface.

__all__ = ("date", "datetime", "time", "timedelta", "timezone", "tzinfo",
           "MINYEAR", "MAXYEAR", "UTC")


import time as _time
import math as _math
import sys
from typing import NamedTuple  # Pystachy port: IsoCalendarDate and _struct_time below
# Pystachy port: operator.index() is not imported: the date and time fields are annotated int

def _cmp(x, y):
    return 0 if x == y else 1 if x > y else -1

def _get_class_module(self):
    # Pystachy port: Pystachy objects have no __class__; the classes are this module's
    return 'datetime'

MINYEAR = 1
MAXYEAR = 9999
_MAXORDINAL = 3652059  # date.max.toordinal()

# Utility functions, adapted from Python's Demo/classes/Dates.py, which
# also assumes the current Gregorian calendar indefinitely extended in
# both directions.  Difference:  Dates.py calls January 1 of year 0 day
# number 1.  The code here calls January 1 of year 1 day number 1.  This is
# to match the definition of the "proleptic Gregorian" calendar in Dershowitz
# and Reingold's "Calendrical Calculations", where it's the base calendar
# for all computations.  See the book for algorithms for converting between
# proleptic Gregorian ordinals and many other calendar systems.

# -1 is a placeholder for indexing purposes.
_DAYS_IN_MONTH = [-1, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

_DAYS_BEFORE_MONTH = [-1]  # -1 is a placeholder for indexing purposes.
dbm = 0
for dim in _DAYS_IN_MONTH[1:]:
    _DAYS_BEFORE_MONTH.append(dbm)
    dbm += dim
del dbm, dim

def _is_leap(year):
    "year -> 1 if leap year, else 0."
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

def _days_before_year(year):
    "year -> number of days before January 1st of year."
    y = year - 1
    return y*365 + y//4 - y//100 + y//400

def _days_in_month(year, month):
    "year, month -> number of days in that month in that year."
    assert 1 <= month <= 12, month
    if month == 2 and _is_leap(year):
        return 29
    return _DAYS_IN_MONTH[month]

def _days_before_month(year, month):
    "year, month -> number of days in year preceding first day of month."
    assert 1 <= month <= 12, 'month must be in 1..12'
    return _DAYS_BEFORE_MONTH[month] + (month > 2 and _is_leap(year))

def _ymd2ord(year, month, day):
    "year, month, day -> ordinal, considering 01-Jan-0001 as day 1."
    assert 1 <= month <= 12, 'month must be in 1..12'
    dim = _days_in_month(year, month)
    assert 1 <= day <= dim, ('day must be in 1..%d' % dim)
    return (_days_before_year(year) +
            _days_before_month(year, month) +
            day)

_DI400Y = _days_before_year(401)    # number of days in 400 years
_DI100Y = _days_before_year(101)    #    "    "   "   " 100   "
_DI4Y   = _days_before_year(5)      #    "    "   "   "   4   "

# A 4-year cycle has an extra leap day over what we'd get from pasting
# together 4 single years.
assert _DI4Y == 4 * 365 + 1

# Similarly, a 400-year cycle has an extra leap day over what we'd get from
# pasting together 4 100-year cycles.
assert _DI400Y == 4 * _DI100Y + 1

# OTOH, a 100-year cycle has one fewer leap day than we'd get from
# pasting together 25 4-year cycles.
assert _DI100Y == 25 * _DI4Y - 1

def _ord2ymd(n):
    "ordinal -> (year, month, day), considering 01-Jan-0001 as day 1."

    # n is a 1-based index, starting at 1-Jan-1.  The pattern of leap years
    # repeats exactly every 400 years.  The basic strategy is to find the
    # closest 400-year boundary at or before n, then work with the offset
    # from that boundary to n.  Life is much clearer if we subtract 1 from
    # n first -- then the values of n at 400-year boundaries are exactly
    # those divisible by _DI400Y:
    #
    #     D  M   Y            n              n-1
    #     -- --- ----        ----------     ----------------
    #     31 Dec -400        -_DI400Y       -_DI400Y -1
    #      1 Jan -399         -_DI400Y +1   -_DI400Y      400-year boundary
    #     ...
    #     30 Dec  000        -1             -2
    #     31 Dec  000         0             -1
    #      1 Jan  001         1              0            400-year boundary
    #      2 Jan  001         2              1
    #      3 Jan  001         3              2
    #     ...
    #     31 Dec  400         _DI400Y        _DI400Y -1
    #      1 Jan  401         _DI400Y +1     _DI400Y      400-year boundary
    n -= 1
    n400, n = divmod(n, _DI400Y)
    year = n400 * 400 + 1   # ..., -399, 1, 401, ...

    # Now n is the (non-negative) offset, in days, from January 1 of year, to
    # the desired date.  Now compute how many 100-year cycles precede n.
    # Note that it's possible for n100 to equal 4!  In that case 4 full
    # 100-year cycles precede the desired day, which implies the desired
    # day is December 31 at the end of a 400-year cycle.
    n100, n = divmod(n, _DI100Y)

    # Now compute how many 4-year cycles precede it.
    n4, n = divmod(n, _DI4Y)

    # And now how many single years.  Again n1 can be 4, and again meaning
    # that the desired day is December 31 at the end of the 4-year cycle.
    n1, n = divmod(n, 365)

    year += n100 * 100 + n4 * 4 + n1
    if n1 == 4 or n100 == 4:
        assert n == 0
        return year-1, 12, 31

    # Now the year is correct, and n is the offset from January 1.  We find
    # the month via an estimate that's either exact or one too large.
    leapyear = n1 == 3 and (n4 != 24 or n100 == 3)
    assert leapyear == _is_leap(year)
    month = (n + 50) >> 5
    preceding = _DAYS_BEFORE_MONTH[month] + (month > 2 and leapyear)
    if preceding > n:  # estimate is too large
        month -= 1
        preceding -= _DAYS_IN_MONTH[month] + (month == 2 and leapyear)
    n -= preceding
    assert 0 <= n < _days_in_month(year, month)

    # Now the year and month are correct, and n is the offset from the
    # start of that month:  we're done!
    return year, month, n+1

# Month and day names.  For localized versions, see the calendar module.
_MONTHNAMES = [None, "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_DAYNAMES = [None, "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# Pystachy port: Pystachy's time module has no struct_time. The time tuples here have its nine
# fields, item access and repr (tm_zone and tm_gmtoff are not provided).
class _struct_time(NamedTuple):
    tm_year: int
    tm_mon: int
    tm_mday: int
    tm_hour: int
    tm_min: int
    tm_sec: int
    tm_wday: int
    tm_yday: int
    tm_isdst: int

    def __repr__(self) -> str:
        return ("time.struct_time(tm_year=%d, tm_mon=%d, tm_mday=%d, tm_hour=%d, tm_min=%d, "
                "tm_sec=%d, tm_wday=%d, tm_yday=%d, tm_isdst=%d)"
                % (self.tm_year, self.tm_mon, self.tm_mday, self.tm_hour, self.tm_min,
                   self.tm_sec, self.tm_wday, self.tm_yday, self.tm_isdst))

def _build_struct_time(y, m, d, hh, mm, ss, dstflag):
    wday = (_ymd2ord(y, m, d) + 6) % 7
    dnum = _days_before_month(y, m) + d
    return _struct_time(y, m, d, hh, mm, ss, wday, dnum, dstflag)  # Pystachy port: (see above)

def _format_time(hh, mm, ss, us, timespec='auto'):
    # Pystachy port: str.format() is not supported, and a % format must be a literal, so the
    # specs dict of format strings is these branches
    if timespec == 'auto':
        # Skip trailing microseconds when us==0.
        timespec = 'microseconds' if us else 'seconds'
    elif timespec == 'milliseconds':
        us //= 1000
    if timespec == 'hours':
        return '%02d' % hh
    if timespec == 'minutes':
        return '%02d:%02d' % (hh, mm)
    if timespec == 'seconds':
        return '%02d:%02d:%02d' % (hh, mm, ss)
    if timespec == 'milliseconds':
        return '%02d:%02d:%02d.%03d' % (hh, mm, ss, us)
    if timespec == 'microseconds':
        return '%02d:%02d:%02d.%06d' % (hh, mm, ss, us)
    raise ValueError('Unknown timespec value')

def _format_offset(off, sep=':'):
    s = ''
    if off is not None:
        if off.days < 0:
            sign = "-"
            off = -off
        else:
            sign = "+"
        # Pystachy port: format_utcoffset() of _datetimemodule.c splits the offset's seconds,
        # as hh and mm cannot be the quotient and the remainder timedelta of divmod() in turn
        mm, ss = divmod(off.seconds, 60)
        hh, mm = divmod(mm, 60)
        s += "%s%02d%s%02d" % (sign, hh, sep, mm)
        if ss or off.microseconds:
            s += "%s%02d" % (sep, ss)

            if off.microseconds:
                s += '.%06d' % off.microseconds
    return s

# Pystachy port: the replacements of _datetimemodule.c's wrap_strftime(), which test the
# object's class (Pystachy has no getattr())
def _zreplacement(object, sep):
    if isinstance(object, datetime):
        return _format_offset(object.utcoffset(), sep)
    if isinstance(object, time):
        return _format_offset(object.utcoffset(), sep)
    return ""

def _Zreplacement(object):
    if isinstance(object, datetime):
        return _escape_tzname(object.tzname())
    if isinstance(object, time):
        return _escape_tzname(object.tzname())
    return ""

def _escape_tzname(s: str | None) -> str:
    if s is None:
        return ""
    # strftime is going to have at this: escape %
    return s.replace('%', '%%')

def _freplacement(object):
    if isinstance(object, datetime):
        return '%06d' % object.microsecond
    if isinstance(object, time):
        return '%06d' % object.microsecond
    return '000000'

# Correctly substitute for %z and %Z escapes in strftime formats.
def _wrap_strftime(object, format, timetuple):
    # Pystachy port: this scan follows wrap_strftime() of _datetimemodule.c, which differs
    # from _pydatetime's for a % followed by another character (it then goes on after that
    # character: "%:%z" formats the offset)
    # Don't call utcoffset() or tzname() unless actually needed.
    freplace: str | None = None  # the string to use for %f
    zreplace: str | None = None  # the string to use for %z
    colonzreplace: str | None = None  # the string to use for %:z
    Zreplace: str | None = None  # the string to use for %Z

    # Scan format for %z, %:z, %Z and %f escapes, replacing as needed.
    newformat: list[str] = []
    push = newformat.append
    i, n = 0, len(format)
    start = 0
    while i < n:
        ch = format[i]
        i += 1
        if ch != '%' or i == n:
            continue
        end = i - 1
        ch = format[i]
        i += 1
        if ch == 'z':
            if zreplace is None:
                zreplace = _zreplacement(object, "")
            replacement = zreplace
        elif ch == ':' and i < n and format[i] == 'z':
            i += 1
            if colonzreplace is None:
                colonzreplace = _zreplacement(object, ":")
            replacement = colonzreplace
        elif ch == 'Z':
            if Zreplace is None:
                Zreplace = _Zreplacement(object)
            replacement = Zreplace
        elif ch == 'f':
            if freplace is None:
                freplace = _freplacement(object)
            replacement = freplace
        else:
            continue
        push(format[start:end])
        push(replacement)
        start = i
    push(format[start:])
    return _strftime("".join(newformat), timetuple)

# Pystachy port: Pystachy's time module has no strftime(). CPython's time.strftime() passes
# each run of ASCII characters of the format to the C library's wcsftime(), and copies the
# others, as _strftime() does below. _strftime_ascii() formats an ASCII run as glibc's
# strftime() does in the C locale, which CPython uses unless the program sets LC_TIME.
_ABDAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
_DAY = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
_ABMON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MON = ["January", "February", "March", "April", "May", "June", "July", "August",
        "September", "October", "November", "December"]

def _iso_week_days(yday: int, wday: int) -> int:
    # glibc's iso_week_days(): the days from the Monday that begins week 1 of the ISO year
    return yday - (yday - wday + 4 + (366 // 7 + 2) * 7) % 7 + 3

def _strftime_ascii(fmt: str, t: _struct_time, limit: int) -> str | None:
    # A struct tm counts months from 0, week days from Sunday and year days from 0.
    # A result that would not fit in limit characters is None (time.strftime()'s buffer).
    year = t.tm_year
    mon = t.tm_mon - 1
    wday = (t.tm_wday + 1) % 7
    yday = t.tm_yday - 1
    hour = t.tm_hour
    out: list[str] = []
    i = 0
    n = len(fmt)
    while i < n:
        c = fmt[i]
        if c != "%":
            out.append(c)
            i += 1
            continue
        start = i
        i += 1
        pad = ""            # the flags: '_', '-' or '0'
        upcase = False      # '^'
        change_case = False  # '#'
        while i < n:
            f = fmt[i]
            if f == "_" or f == "-" or f == "0":
                pad = f
            elif f == "^":
                upcase = True
            elif f == "#":
                change_case = True
            else:
                break
            i += 1
        width = -1
        if i < n and fmt[i].isdigit():
            width = 0
            while i < n and fmt[i].isdigit():
                width = width * 10 + int(fmt[i])
                if width > 2147483647:
                    width = 2147483647
                i += 1
        modifier = ""
        if i < n and (fmt[i] == "E" or fmt[i] == "O"):
            modifier = fmt[i]
            i += 1
        conv = ""
        if i < n:
            conv = fmt[i]
        i += 1
        if i > n:
            i = n  # (a % at the end of the format: glibc copies what follows it)
        text = ""        # a text result,
        number = -1      # or a number of at least digits digits,
        digits = 0
        spacepad = False
        lowcase = False
        bad = False      # or the conversion as it is written
        subfmt = ""      # or a format for these fields
        if conv == "%":
            bad = modifier != ""
            text = "%"
        elif conv == "a" or conv == "A":
            bad = modifier != ""
            if change_case and not bad:
                upcase = True
            text = _ABDAY[wday] if conv == "a" else _DAY[wday]
        elif conv == "b" or conv == "h" or conv == "B":
            bad = modifier == "E"
            if change_case and (not bad or conv != "B"):
                upcase = True
            text = _MON[mon] if conv == "B" else _ABMON[mon]
        elif conv == "c":
            bad = modifier == "O"
            subfmt = "%a %b %e %H:%M:%S %Y"
        elif conv == "C":
            number = year // 100
            digits = 1
        elif conv == "x" or conv == "D":
            bad = modifier == "O" if conv == "x" else modifier != ""
            subfmt = "%m/%d/%y"
        elif conv == "d" or conv == "e":
            bad = modifier == "E"
            number = t.tm_mday
            digits = 2
            spacepad = conv == "e"
        elif conv == "F":
            bad = modifier != ""
            subfmt = "%Y-%m-%d"
        elif conv == "H" or conv == "k":
            bad = modifier == "E"
            number = hour
            digits = 2
            spacepad = conv == "k"
        elif conv == "I" or conv == "l":
            bad = modifier == "E"
            number = (hour + 11) % 12 + 1
            digits = 2
            spacepad = conv == "l"
        elif conv == "j":
            bad = modifier == "E"
            number = yday + 1
            digits = 3
        elif conv == "M":
            bad = modifier == "E"
            number = t.tm_min
            digits = 2
        elif conv == "m":
            bad = modifier == "E"
            number = mon + 1
            digits = 2
        elif conv == "n":
            text = "\n"
        elif conv == "t":
            text = "\t"
        elif conv == "P" or conv == "p":
            lowcase = conv == "P"
            if change_case:
                upcase = False
                lowcase = True
            text = "AM" if hour < 12 else "PM"
        elif conv == "R":
            subfmt = "%H:%M"
        elif conv == "r":
            subfmt = "%I:%M:%S %p"
        elif conv == "S":
            bad = modifier == "E"
            number = t.tm_sec
            digits = 2
        elif conv == "s":
            # (mktime(), in the local time zone)
            raise NotImplementedError("strftime(): %s needs the local time zone, which "
                                      "Pystachy's time module does not provide")
        elif conv == "X" or conv == "T":
            bad = modifier == "O" if conv == "X" else False
            subfmt = "%H:%M:%S"
        elif conv == "u":
            number = (wday - 1 + 7) % 7 + 1
            digits = 1
        elif conv == "U":
            bad = modifier == "E"
            number = (yday - wday + 7) // 7
            digits = 2
        elif conv == "V" or conv == "g" or conv == "G":
            bad = modifier == "E"
            iso_year = year
            days = _iso_week_days(yday, wday)
            if days < 0:
                # This ISO week belongs to the previous year.
                iso_year -= 1
                days = _iso_week_days(yday + (365 + _is_leap(iso_year)), wday)
            else:
                d = _iso_week_days(yday - (365 + _is_leap(year)), wday)
                if d >= 0:
                    # This ISO week belongs to the next year.
                    iso_year += 1
                    days = d
            if conv == "g":
                number = iso_year % 100
                digits = 2
            elif conv == "G":
                number = iso_year
                digits = 1
            else:
                number = days // 7 + 1
                digits = 2
        elif conv == "W":
            bad = modifier == "E"
            number = (yday - (wday - 1 + 7) % 7 + 7) // 7
            digits = 2
        elif conv == "w":
            bad = modifier == "E"
            number = wday
            digits = 1
        elif conv == "Y":
            bad = modifier == "O"
            number = year
            digits = 1
        elif conv == "y":
            number = year % 100
            digits = 2
        elif conv == "Z":
            # (only with flags or a width, as _wrap_strftime() replaces %Z: tm_zone is NULL, so
            # glibc names the local time zone where tm_isdst >= 0; the name is padded as it is)
            if t.tm_isdst >= 0:
                raise NotImplementedError("strftime(): this %Z needs the local time zone, "
                                          "which Pystachy's time module does not provide")
            w = 0 if pad == "-" or width < 0 else width
            if w >= limit:
                return None
            out.append(("0" if pad == "0" else " ") * w)
            continue
        elif conv == "z":
            if t.tm_isdst < 0:
                continue
            # (tm_gmtoff is 0: the sign, width-padded alone, then the number 0000)
            if width >= limit:
                return None
            if width > 1:
                out.append(("0" if pad == "0" else " ") * (width - 1))
            out.append("+")
            number = 0
            digits = 4
        else:
            bad = True
        if bad:
            # glibc copies the conversion from its '%' (a '%' conversion is the '%' alone)
            text = "%" if conv == "%" else fmt[start:i]
            number = -1
            subfmt = ""
            lowcase = False
        elif subfmt != "":
            sub = _strftime_ascii(subfmt, t, limit)
            if sub is None:
                return None
            text = sub
        elif number >= 0:
            if width > digits:
                digits = width
            if digits >= limit:
                return None
            text = str(number)
            padding = digits - len(text)
            if spacepad and pad != "0" and pad != "-":
                pad = "_"
            if pad != "-" and padding > 0:
                if pad == "_":
                    out.append(" " * padding)
                    width = width - padding if width > padding else 0
                else:
                    text = "0" * padding + text
                    width = 0
        if width >= limit or len(text) >= limit:
            return None
        if lowcase:
            text = text.lower()
        elif upcase:
            text = text.upper()
        if width > len(text):
            out.append(("0" if pad == "0" else " ") * (width - len(text)))
        out.append(text)
    return "".join(out)

def _strftime(format: str, timetuple: _struct_time) -> str:
    out: list[str] = []
    i = 0
    n = len(format)
    size = 1024  # (time.strftime()'s buffer, which an empty or long result grows)
    while i < n:
        j = i
        while j < n and format[j] != "\0" and format[j].isascii():
            j += 1
        if j > i:
            cap = size
            while cap < 256 * (j - i):
                cap += cap
            r = _strftime_ascii(format[i:j], timetuple, cap)
            if r is None:
                size = cap
            else:
                while size < 256 * (j - i) and (len(r) == 0 or len(r) >= size):
                    size += size
                if len(r) < size:
                    out.append(r)  # (else it does not fit: CPython gives "")
        i = j
        while j < n and format[j] != "%":
            j += 1
        out.append(format[i:j])
        i = j
    return "".join(out)

# Helpers for parsing the result of isoformat()
def _is_ascii_digit(c):
    return c in "0123456789"

def _find_isoformat_datetime_separator(dtstr):
    # See the comment in _datetimemodule.c:_find_isoformat_datetime_separator
    len_dtstr = len(dtstr)
    if len_dtstr == 7:
        return 7

    assert len_dtstr > 7
    date_separator = "-"
    week_indicator = "W"

    if dtstr[4] == date_separator:
        if dtstr[5] == week_indicator:
            if len_dtstr < 8:
                raise ValueError("Invalid ISO string")
            if len_dtstr > 8 and dtstr[8] == date_separator:
                if len_dtstr == 9:
                    raise ValueError("Invalid ISO string")
                if len_dtstr > 10 and _is_ascii_digit(dtstr[10]):
                    # This is as far as we need to resolve the ambiguity for
                    # the moment - if we have YYYY-Www-##, the separator is
                    # either a hyphen at 8 or a number at 10.
                    #
                    # We'll assume it's a hyphen at 8 because it's way more
                    # likely that someone will use a hyphen as a separator than
                    # a number, but at this point it's really best effort
                    # because this is an extension of the spec anyway.
                    # TODO(pganssle): Document this
                    return 8
                return 10
            else:
                # YYYY-Www (8)
                return 8
        else:
            # YYYY-MM-DD (10)
            return 10
    else:
        if dtstr[4] == week_indicator:
            # YYYYWww (7) or YYYYWwwd (8)
            idx = 7
            while idx < len_dtstr:
                if not _is_ascii_digit(dtstr[idx]):
                    break
                idx += 1

            if idx < 9:
                return idx

            if idx % 2 == 0:
                # If the index of the last number is even, it's YYYYWwwd
                return 7
            else:
                return 8
        else:
            # YYYYMMDD (8)
            return 8


# Pystachy port: the ISO 8601 parsers below are those of _datetimemodule.c, which CPython runs
# and which accept and reject other strings than _pydatetime's (e.g. "20200101" as a time,
# or "12:00Z00"). They read the string as C reads its UTF-8 bytes, ending in a NUL: _c_at()
# is "\0" past its end. Each returns C's code first: negative for an invalid string.
def _c_at(s: str, i: int) -> str:
    return s[i] if i < len(s) else "\0"

def _parse_digits(s: str, i: int, n: int) -> tuple[int, int]:
    # parse_digits(): the value of the n digits at i, and the index after them (-1 if one
    # is not a digit)
    v = 0
    for _ in range(n):
        c = _c_at(s, i)
        i += 1
        if not "0" <= c <= "9":
            return 0, -1
        v = v * 10 + int(c)
    return v, i

def _parse_isoformat_date(dtstr: str, length: int) -> tuple[int, int, int, int]:
    # parse_isoformat_date(): the code, year, month and day of the date in dtstr[:length]
    year, p = _parse_digits(dtstr, 0, 4)
    if p < 0:
        return -1, 0, 0, 0
    uses_separator = _c_at(dtstr, p) == '-'
    if uses_separator:
        p += 1

    if _c_at(dtstr, p) == 'W':
        # This is an isocalendar-style date string
        p += 1
        iso_week, p = _parse_digits(dtstr, p, 2)
        if p < 0:
            return -3, 0, 0, 0
        if p < length:
            if uses_separator:
                c = _c_at(dtstr, p)
                p += 1
                if c != '-':
                    return -2, 0, 0, 0
            iso_day, p = _parse_digits(dtstr, p, 1)
            if p < 0:
                return -4, 0, 0, 0
        else:
            iso_day = 1
        try:
            y, m, d = _isoweek_to_gregorian(year, iso_week, iso_day)
        except ValueError:
            return -5, 0, 0, 0
        return 0, y, m, d

    month, p = _parse_digits(dtstr, p, 2)
    if p < 0:
        return -1, 0, 0, 0
    if uses_separator:
        c = _c_at(dtstr, p)
        p += 1
        if c != '-':
            return -2, 0, 0, 0
    day, p = _parse_digits(dtstr, p, 2)
    if p < 0:
        return -1, 0, 0, 0
    return 0, year, month, day


_FRACTION_CORRECTION = [100000, 10000, 1000, 100, 10]


def _parse_hh_mm_ss_ff(tstr: str, p: int, p_end: int) -> tuple[int, int, int, int, int]:
    # parse_hh_mm_ss_ff(): the code, hour, minute, second and microsecond of
    # HH[:?MM[:?SS[{.,}fff[fff]]]] in tstr[p:p_end]
    vals = [0, 0, 0]
    has_separator = True
    i = 0
    while i < 3:
        v, p = _parse_digits(tstr, p, 2)
        if p < 0:
            return -3, 0, 0, 0, 0
        vals[i] = v
        c = _c_at(tstr, p)
        p += 1
        if i == 0:
            has_separator = c == ':'
        if c == '.' or c == ',':
            if p >= p_end:
                return -3, 0, 0, 0, 0  # Decimal mark not followed by any digit
            break
        elif p >= p_end:
            return int(c != '\0'), vals[0], vals[1], vals[2], 0
        elif has_separator and c == ':':
            i += 1
            continue
        elif not has_separator:
            p -= 1
        else:
            return -4, 0, 0, 0, 0  # Malformed time separator
        i += 1

    # Parse fractional components
    to_parse = p_end - p
    if to_parse >= 6:
        to_parse = 6
    microsecond, p = _parse_digits(tstr, p, to_parse)
    if p < 0:
        return -3, 0, 0, 0, 0
    if to_parse < 6:
        microsecond *= _FRACTION_CORRECTION[to_parse-1]
    while "0" <= _c_at(tstr, p) <= "9":
        p += 1  # skip truncated digits

    # 1 if it's not the end of the string
    return int(_c_at(tstr, p) != '\0'), vals[0], vals[1], vals[2], microsecond

def _parse_isoformat_time(dtstr: str, p: int) -> tuple[int, int, int, int, int, int, int]:
    # parse_isoformat_time(): the code (1 with an offset), hour, minute, second, microsecond,
    # and offset seconds and microseconds of the time in dtstr[p:]
    p_end = len(dtstr)
    tzinfo_pos = p
    while True:
        c = _c_at(dtstr, tzinfo_pos)
        if c == 'Z' or c == '+' or c == '-':
            break
        tzinfo_pos += 1
        if tzinfo_pos >= p_end:
            break

    rv, hour, minute, second, microsecond = _parse_hh_mm_ss_ff(dtstr, p, tzinfo_pos)
    if rv < 0:
        return rv, 0, 0, 0, 0, 0, 0
    elif tzinfo_pos == p_end:
        # We know that there's no time zone, so if there's stuff at the
        # end of the string it's an error.
        if rv == 1:
            return -5, 0, 0, 0, 0, 0, 0
        return 0, hour, minute, second, microsecond, 0, 0

    # Special case UTC / Zulu time.
    if _c_at(dtstr, tzinfo_pos) == 'Z':
        if _c_at(dtstr, tzinfo_pos + 1) != '\0':
            return -5, 0, 0, 0, 0, 0, 0
        return 1, hour, minute, second, microsecond, 0, 0

    tzsign = -1 if _c_at(dtstr, tzinfo_pos) == '-' else 1
    rv, tzhour, tzminute, tzsecond, tzmicrosecond = _parse_hh_mm_ss_ff(
        dtstr, tzinfo_pos + 1, p_end)
    if rv:
        return -5, 0, 0, 0, 0, 0, 0
    return (1, hour, minute, second, microsecond,
            tzsign * (tzhour * 3600 + tzminute * 60 + tzsecond), tzsign * tzmicrosecond)

def _tzinfo_from_isoformat(rv: int, tzoffset: int, tzmicrosecond: int) -> 'timezone | None':
    # tzinfo_from_isoformat_results(): the parsed time zone, whose offset can be out of
    # range (a ValueError, rather than "Invalid isoformat string")
    if rv == 1:
        if tzoffset == 0 and tzmicrosecond == 0:
            return timezone.utc
        return timezone(timedelta(0, tzoffset, tzmicrosecond))
    return None


# tuple[int, int, int] -> tuple[int, int, int] version of date.fromisocalendar
def _isoweek_to_gregorian(year, week, day):
    # Year is bounded this way because 9999-12-31 is (9999, 52, 5)
    if not MINYEAR <= year <= MAXYEAR:
        raise ValueError(f"Year is out of range: {year}")

    if not 0 < week < 53:
        out_of_range = True

        if week == 53:
            # ISO years have 53 weeks in them on years starting with a
            # Thursday and leap years starting on a Wednesday
            first_weekday = _ymd2ord(year, 1, 1) % 7
            if (first_weekday == 4 or (first_weekday == 3 and
                                       _is_leap(year))):
                out_of_range = False

        if out_of_range:
            raise ValueError(f"Invalid week: {week}")

    if not 0 < day < 8:
        raise ValueError(f"Invalid day: {day} (range is [1, 7])")  # Pystachy port: _datetime's

    # Now compute the offset from (Y, 1, 1) in days:
    day_offset = (week - 1) * 7 + (day - 1)

    # Calculate the ordinal day for monday, week 1
    day_1 = _isoweek1monday(year)
    ord_day = day_1 + day_offset

    return _ord2ymd(ord_day)


# Just raise TypeError if the arg isn't None or a string.
def _check_tzname(name):
    # Pystachy port: name is a str or None by its type, the method's result
    pass

# name is the offset-producing method, "utcoffset" or "dst".
# offset is what it returned.
# If offset isn't None or timedelta, raises TypeError.
# If offset is None, returns None.
# Else offset is checked for being in range.
# If it is, its integer value is returned.  Else ValueError is raised.
def _check_utc_offset(name, offset):
    assert name in ("utcoffset", "dst")
    if offset is None:
        return
    # Pystachy port: offset is a timedelta by its type, and the message is _datetime's
    if not -timedelta(1) < offset < timedelta(1):
        raise ValueError("offset must be a timedelta strictly between "
                         "-timedelta(hours=24) and timedelta(hours=24).")

def _check_date_fields(year: int, month: int, day: int):
    # Pystachy port: the fields are ints by their annotations (no operator.index()), and the
    # messages are _datetime's
    if not MINYEAR <= year <= MAXYEAR:
        raise ValueError('year %d is out of range' % year)
    if not 1 <= month <= 12:
        raise ValueError('month must be in 1..12')
    dim = _days_in_month(year, month)
    if not 1 <= day <= dim:
        raise ValueError('day is out of range for month')
    return year, month, day

def _check_time_fields(hour: int, minute: int, second: int, microsecond: int, fold: int):
    # Pystachy port: (see _check_date_fields())
    if not 0 <= hour <= 23:
        raise ValueError('hour must be in 0..23')
    if not 0 <= minute <= 59:
        raise ValueError('minute must be in 0..59')
    if not 0 <= second <= 59:
        raise ValueError('second must be in 0..59')
    if not 0 <= microsecond <= 999999:
        raise ValueError('microsecond must be in 0..999999')
    if fold not in (0, 1):
        raise ValueError('fold must be either 0 or 1')
    return hour, minute, second, microsecond, fold

def _check_tzinfo_arg(tz):
    if tz is not None and not isinstance(tz, tzinfo):
        raise TypeError("tzinfo argument must be None or of a tzinfo subclass")

def _divide_and_round(a, b):
    """divide a by b and round result to the nearest integer

    When the ratio is exactly half-way between two integers,
    the even integer is returned.
    """
    # Based on the reference implementation for divmod_near
    # in Objects/longobject.c.
    q, r = divmod(a, b)
    # round up if either r / b > 0.5, or r / b == 0.5 and q is odd.
    # The expression r / b > 0.5 is equivalent to 2 * r > b if b is
    # positive, 2 * r < b if b negative.
    r *= 2
    greater_than_half = r > b if b > 0 else r < b
    if greater_than_half or r == b and q % 2 == 1:
        q += 1

    return q


# Pystachy port: integers are 64-bit, so the exact products and quotients below, which
# CPython computes with its long integers, use little-endian lists of 8-bit digits.
def _big(n: int) -> list[int]:
    # n >= 0
    digits: list[int] = []
    while n:
        digits.append(n & 255)
        n >>= 8
    return digits

def _big_mul(a: list[int], m: int) -> list[int]:
    # a * m, for 0 <= m < 2**53
    out: list[int] = []
    carry = 0
    for x in a:
        v = x * m + carry
        out.append(v & 255)
        carry = v >> 8
    while carry:
        out.append(carry & 255)
        carry >>= 8
    return out

def _big_shl(a: list[int], k: int) -> list[int]:
    # a * 2**k
    return _big_mul([0] * (k // 8) + a, 1 << (k % 8))

def _big_divmod(a: list[int], d: int) -> tuple[list[int], int]:
    # divmod(a, d), for 0 < d < 2**53
    q = [0] * len(a)
    r = 0
    i = len(a) - 1
    while i >= 0:
        v = (r << 8) | a[i]
        q[i] = v // d
        r = v % d
        i -= 1
    return q, r

def _big_bit(a: list[int], k: int) -> int:
    return (a[k // 8] >> (k % 8)) & 1 if k // 8 < len(a) else 0

def _big_shr_round(a: list[int], k: int) -> list[int]:
    # a / 2**k, rounded half to even, for k > 0
    q, _ = _big_divmod(a[k // 8:], 1 << (k % 8))
    half = _big_bit(a, k - 1)
    sticky = False  # (a bit below the halfway bit)
    j = 0
    while not sticky and j < (k - 1) // 8 and j < len(a):
        sticky = a[j] != 0
        j += 1
    if (k - 1) // 8 < len(a) and a[(k - 1) // 8] & ((1 << ((k - 1) % 8)) - 1):
        sticky = True
    if half and (sticky or (len(q) > 0 and q[0] & 1)):
        q = _big_add1(q)
    return q

def _big_add1(a: list[int]) -> list[int]:
    out = a[:]
    i = 0
    while i < len(out):
        if out[i] < 255:
            out[i] += 1
            return out
        out[i] = 0
        i += 1
    out.append(1)
    return out

def _big_to_delta(a: list[int], negative: bool) -> 'timedelta':
    # microseconds_to_delta() of _datetimemodule.c: the timedelta of a (or -a) microseconds
    q, us = _big_divmod(a, 86400 * 10**6)
    while q and q[-1] == 0:
        q.pop()
    if len(q) > 4:
        raise OverflowError("Python int too large to convert to C int")
    d = 0
    for x in reversed(q):
        d = (d << 8) | x
    if negative:
        d = -d
        if us:
            d -= 1
            us = 86400 * 10**6 - us
    if not -2147483648 <= d <= 2147483647:
        raise OverflowError("Python int too large to convert to C int")
    return timedelta(d, 0, us)

def _scale_delta(usec: int, x: float, divide: bool) -> 'timedelta':
    # multiply_truedivide_timedelta_float() of _datetimemodule.c: the timedelta of usec * x,
    # or usec / x, microseconds rounded half to even, with x exactly as as_integer_ratio()
    # gives it
    if x != x:
        raise ValueError("cannot convert NaN to integer ratio")
    if x == _math.inf or x == -_math.inf:
        raise OverflowError("cannot convert Infinity to integer ratio")
    if divide and x == 0.0:
        raise ZeroDivisionError("integer division or modulo by zero")
    negative = (usec < 0) != (x < 0.0)
    if usec < 0:
        usec = -usec
    frac, e = _math.frexp(abs(x))
    m = int(frac * 9007199254740992.0)  # x = m * 2**(e - 53), m < 2**53
    e -= 53
    if usec == 0 or m == 0:
        return timedelta(0)
    if not divide:
        n = _big_mul(_big(usec), m)
        r = _big_shl(n, e) if e >= 0 else _big_shr_round(n, -e)
    elif e <= 0:
        q, rem = _big_divmod(_big_shl(_big(usec), -e), m)
        if 2 * rem > m or (2 * rem == m and q and q[0] & 1):
            q = _big_add1(q)
        r = q
    else:
        # usec / (m * 2**e) < 2**11: round (q1 + r1/m) / 2**e
        q1, r1 = divmod(usec, m)
        if e > 12:
            return timedelta(0)
        whole = q1 >> e
        rest = q1 & ((1 << e) - 1)
        half = 1 << (e - 1)
        if rest > half or (rest == half and (r1 or whole & 1)):
            whole += 1
        r = _big(whole)
    return _big_to_delta(r, negative)

def _c_round(x: float) -> float:
    # C's round(): halfway cases away from zero
    if x < 0.0:
        return -_c_round(-x)
    frac = _math.fmod(x, 1.0)
    r = x - frac
    if frac >= 0.5:
        r += 1.0
    return r

def _accum(d: int, us: int, leftover: float, num, factor: int,
           per_day: int) -> tuple[int, int, float]:
    # accum() of _datetimemodule.c: adds num units of factor microseconds to the running
    # total of d days and us microseconds, and the fraction of a microsecond that a float
    # gives to leftover. per_day is the units in a day (0 for weeks, of 7 days).
    if isinstance(num, float):
        fracpart, intpart = _math.modf(num)
        if intpart != intpart:
            raise ValueError("cannot convert float NaN to integer")
        if not -9.223372036854776e18 <= intpart < 9.223372036854776e18:
            if intpart == _math.inf or intpart == -_math.inf:
                raise OverflowError("cannot convert float infinity to integer")
            raise OverflowError("Python int too large to convert to C int")
        d, us, leftover = _accum(d, us, leftover, int(intpart), factor, per_day)
        if fracpart == 0.0:
            return d, us, leftover
        fracpart, intpart = _math.modf(float(factor) * fracpart)
        us += int(intpart)
        return d, us, leftover + fracpart
    if per_day == 0:
        return d + num * 7, us, leftover
    days, rest = divmod(num, per_day)
    return d + days, us + rest * factor, leftover

class timedelta:
    """Represent the difference between two datetime objects.

    Supported operators:

    - add, subtract timedelta
    - unary plus, minus, abs
    - compare to timedelta
    - multiply, divide by int

    In addition, datetime supports subtraction of two datetime objects
    returning a timedelta, and addition or subtraction of a datetime
    and a timedelta giving a datetime.

    Representation: (days, seconds, microseconds).
    """
    # The representation of (days, seconds, microseconds) was chosen
    # arbitrarily; the exact rationale originally specified in the docstring
    # was "Because I felt like it."

    __slots__ = '_days', '_seconds', '_microseconds', '_hashcode'
    # Pystachy port: the class attributes assigned after the class are declared here
    min: 'timedelta | None' = None
    max: 'timedelta | None' = None
    resolution: 'timedelta | None' = None

    # Pystachy port: __init__ rather than __new__, which Pystachy does not call, and the
    # arguments are ints or floats, as the XXX below asks
    def __init__(self, days: int | float = 0, seconds: int | float = 0,
                 microseconds: int | float = 0, milliseconds: int | float = 0,
                 minutes: int | float = 0, hours: int | float = 0,
                 weeks: int | float = 0) -> None:
        # Doing this efficiently and accurately in C is going to be difficult
        # and error-prone, due to ubiquitous overflow possibilities, and that
        # C double doesn't have enough bits of precision to represent
        # microseconds over 10K years faithfully.  The code here tries to make
        # explicit where go-fast assumptions can be relied on, in order to
        # guide the C implementation; it's way more convoluted than speed-
        # ignoring auto-overflow-to-long idiomatic Python could be.

        # Pystachy port: this is delta_new() of _datetimemodule.c, which CPython runs: it adds
        # each argument separately and rounds the fractions of microseconds once, so float
        # arguments can give other microseconds than _pydatetime's normalization. The total
        # is kept as days and microseconds, which fit 64-bit integers.
        d = 0
        us = 0
        leftover = 0.0
        d, us, leftover = _accum(d, us, leftover, microseconds, 1, 86400000000)
        d, us, leftover = _accum(d, us, leftover, milliseconds, 1000, 86400000)
        d, us, leftover = _accum(d, us, leftover, seconds, 1000000, 86400)
        d, us, leftover = _accum(d, us, leftover, minutes, 60000000, 1440)
        d, us, leftover = _accum(d, us, leftover, hours, 3600000000, 24)
        d, us, leftover = _accum(d, us, leftover, days, 86400000000, 1)
        d, us, leftover = _accum(d, us, leftover, weeks, 604800000000, 0)
        if leftover:
            # Round to nearest whole # of us, and add into the total.
            whole_us = _c_round(leftover)
            if abs(whole_us - leftover) == 0.5:
                # We're exactly halfway between two integers.  In order
                # to do round-half-to-even, we must determine whether the
                # total is odd (a day has an even number of microseconds).
                is_odd = us & 1
                whole_us = 2.0 * _c_round((leftover + is_odd) * 0.5) - is_odd
            us += int(whole_us)

        s, us = divmod(us, 1000000)
        days2, s = divmod(s, 24*3600)
        d += days2

        assert isinstance(d, int)
        assert isinstance(s, int) and 0 <= s < 24*3600
        assert isinstance(us, int) and 0 <= us < 1000000

        if not -2147483648 <= d <= 2147483647:
            raise OverflowError("Python int too large to convert to C int")
        if abs(d) > 999999999:
            raise OverflowError("days=%d; must have magnitude <= 999999999" % d)

        # Pystachy port: the fields are annotated, as their values come from _accum()
        self._days: int = d
        self._seconds: int = s
        self._microseconds: int = us
        self._hashcode = -1

    def __repr__(self):
        args = []
        if self._days:
            args.append("days=%d" % self._days)
        if self._seconds:
            args.append("seconds=%d" % self._seconds)
        if self._microseconds:
            args.append("microseconds=%d" % self._microseconds)
        if not args:
            args.append('0')
        return "%s.%s(%s)" % (_get_class_module(self),
                              "timedelta",  # Pystachy port: (no __class__)
                              ', '.join(args))

    def __str__(self):
        mm, ss = divmod(self._seconds, 60)
        hh, mm = divmod(mm, 60)
        s = "%d:%02d:%02d" % (hh, mm, ss)
        if self._days:
            # Pystachy port: plural() returned n and its "s" or "", a tuple for %
            s = ("%d day%s, " % (self._days, "s" if abs(self._days) != 1 else "")) + s
        if self._microseconds:
            s = s + ".%06d" % self._microseconds
        return s

    def total_seconds(self):
        """Total seconds in the duration."""
        return ((self.days * 86400 + self.seconds) * 10**6 +
                self.microseconds) / 10**6

    # Read-only field accessors
    @property
    def days(self) -> int:  # Pystachy port: a property needs its return annotation
        """days"""
        return self._days

    @property
    def seconds(self) -> int:  # Pystachy port: (see days)
        """seconds"""
        return self._seconds

    @property
    def microseconds(self) -> int:  # Pystachy port: (see days)
        """microseconds"""
        return self._microseconds

    # Pystachy port: NotImplemented is not supported. The operator methods take the types
    # that CPython's accept, and a None operand raises the TypeError that CPython raises for
    # it, from _unsupported() and _not_ordered() below.
    def __add__(self, other: 'timedelta') -> 'timedelta':
        if isinstance(other, timedelta):
            # for CPython compatibility, we cannot use
            # our __class__ here, but need a real timedelta
            return timedelta(self._days + other._days,
                             self._seconds + other._seconds,
                             self._microseconds + other._microseconds)
        raise _unsupported("+", self, other)

    # Pystachy port: a method for __radd__ = __add__, annotated; Pystachy does not call the
    # reflected methods (CPython does)
    def __radd__(self, other: 'timedelta') -> 'timedelta':
        return self.__add__(other)

    def __sub__(self, other: 'timedelta') -> 'timedelta':
        if isinstance(other, timedelta):
            # for CPython compatibility, we cannot use
            # our __class__ here, but need a real timedelta
            return timedelta(self._days - other._days,
                             self._seconds - other._seconds,
                             self._microseconds - other._microseconds)
        raise _unsupported("-", self, other)

    def __rsub__(self, other: 'timedelta') -> 'timedelta':  # Pystachy port: (see __radd__)
        if isinstance(other, timedelta):
            return -self + other
        raise _unsupported("-", other, self)

    def __neg__(self) -> 'timedelta':  # Pystachy port: annotated (a special method)
        # for CPython compatibility, we cannot use
        # our __class__ here, but need a real timedelta
        return timedelta(-self._days,
                         -self._seconds,
                         -self._microseconds)

    def __pos__(self) -> 'timedelta':  # Pystachy port: annotated (a special method)
        return self

    def __abs__(self) -> 'timedelta':  # Pystachy port: annotated (a special method)
        if self._days < 0:
            return -self
        else:
            return self

    def __mul__(self, other):
        if isinstance(other, int):
            # for CPython compatibility, we cannot use
            # our __class__ here, but need a real timedelta
            return timedelta(self._days * other,
                             self._seconds * other,
                             self._microseconds * other)
        if isinstance(other, float):
            # Pystachy port: _scale_delta() is usec * a / b, rounded, without long integers
            return _scale_delta(self._to_microseconds(), other, False)
        raise _unsupported("*", self, other)

    def __rmul__(self, other: int | float) -> 'timedelta':  # Pystachy port: (see __radd__)
        return self.__mul__(other)

    def _to_microseconds(self):
        return ((self._days * (24*3600) + self._seconds) * 1000000 +
                self._microseconds)

    def __floordiv__(self, other):
        if not isinstance(other, (int, timedelta)):
            raise _unsupported("//", self, other)  # Pystachy port: (see __add__)
        usec = self._to_microseconds()
        if isinstance(other, timedelta):
            return usec // other._to_microseconds()
        if isinstance(other, int):
            return timedelta(0, 0, usec // other)
        raise _unsupported("//", self, other)  # Pystachy port: (no other case returns None)

    def __truediv__(self, other):
        if not isinstance(other, (int, float, timedelta)):
            raise _unsupported("/", self, other)  # Pystachy port: (see __add__)
        usec = self._to_microseconds()
        if isinstance(other, timedelta):
            return usec / other._to_microseconds()
        if isinstance(other, int):
            return timedelta(0, 0, _divide_and_round(usec, other))
        if isinstance(other, float):
            # Pystachy port: (see __mul__)
            return _scale_delta(usec, other, True)
        raise _unsupported("/", self, other)  # Pystachy port: (see __floordiv__)

    def __mod__(self, other: 'timedelta') -> 'timedelta':
        if isinstance(other, timedelta):
            r = self._to_microseconds() % other._to_microseconds()
            return timedelta(0, 0, r)
        raise _unsupported("%", self, other)

    def __divmod__(self, other: 'timedelta') -> 'tuple[int, timedelta]':
        if isinstance(other, timedelta):
            q, r = divmod(self._to_microseconds(),
                          other._to_microseconds())
            return q, timedelta(0, 0, r)
        raise _unsupported("divmod()", self, other)

    # Comparisons of timedelta objects with other.

    def __eq__(self, other: 'timedelta') -> bool:
        if isinstance(other, timedelta):
            return self._cmp(other) == 0
        else:
            return False  # Pystachy port: None, which is not equal (see __add__)

    def __le__(self, other: 'timedelta') -> bool:
        if isinstance(other, timedelta):
            return self._cmp(other) <= 0
        else:
            raise _not_ordered("<=", self, other)

    def __lt__(self, other: 'timedelta') -> bool:
        if isinstance(other, timedelta):
            return self._cmp(other) < 0
        else:
            raise _not_ordered("<", self, other)

    def __ge__(self, other: 'timedelta') -> bool:
        if isinstance(other, timedelta):
            return self._cmp(other) >= 0
        else:
            raise _not_ordered(">=", self, other)

    def __gt__(self, other: 'timedelta') -> bool:
        if isinstance(other, timedelta):
            return self._cmp(other) > 0
        else:
            raise _not_ordered(">", self, other)

    def _cmp(self, other):
        assert isinstance(other, timedelta)
        return _cmp(self._getstate(), other._getstate())

    def __hash__(self) -> int:  # Pystachy port: annotated
        if self._hashcode == -1:
            self._hashcode = hash(self._getstate())
        return self._hashcode

    def __bool__(self):
        return (self._days != 0 or
                self._seconds != 0 or
                self._microseconds != 0)

    # Pickle support.

    def _getstate(self):
        return (self._days, self._seconds, self._microseconds)

    # Pystachy port: __reduce__() is left out, as Pystachy has no bytes or pickle module

timedelta.min = timedelta(-999999999)
timedelta.max = timedelta(days=999999999, hours=23, minutes=59, seconds=59,
                          microseconds=999999)
timedelta.resolution = timedelta(microseconds=1)

# Pystachy port: the names of the operands' types, for the TypeError of an operation that
# CPython's methods return NotImplemented for (and Pystachy cannot)
def _type_name(x) -> str:
    if x is None:
        return "NoneType"
    if isinstance(x, bool):
        return "bool"
    if isinstance(x, int):
        return "int"
    if isinstance(x, float):
        return "float"
    if isinstance(x, str):
        return "str"
    if isinstance(x, datetime):
        return "datetime.datetime"
    if isinstance(x, date):
        return "datetime.date"
    if isinstance(x, time):
        return "datetime.time"
    if isinstance(x, timedelta):
        return "datetime.timedelta"
    if isinstance(x, timezone):
        return "datetime.timezone"
    if isinstance(x, tzinfo):
        return "datetime.tzinfo"
    return "object"

def _unsupported(op, x, y) -> TypeError:
    if op == "divmod()":
        return TypeError("unsupported operand type(s) for divmod(): '%s' and '%s'"
                         % (_type_name(x), _type_name(y)))
    return TypeError("unsupported operand type(s) for %s: '%s' and '%s'"
                     % (op, _type_name(x), _type_name(y)))

def _not_ordered(op, x, y) -> TypeError:
    return TypeError("'%s' not supported between instances of '%s' and '%s'"
                     % (op, _type_name(x), _type_name(y)))

class date:
    """Concrete date type.

    Constructors:

    __new__()
    fromtimestamp()
    today()
    fromordinal()

    Operators:

    __repr__, __str__
    __eq__, __le__, __lt__, __ge__, __gt__, __hash__
    __add__, __radd__, __sub__ (add/radd only with timedelta arg)

    Methods:

    timetuple()
    toordinal()
    weekday()
    isoweekday(), isocalendar(), isoformat()
    ctime()
    strftime()

    Properties (readonly):
    year, month, day
    """
    __slots__ = '_year', '_month', '_day', '_hashcode'
    # Pystachy port: the class attributes assigned after the class are declared here
    min: 'date | None' = None
    max: 'date | None' = None
    resolution: 'timedelta | None' = None

    # Pystachy port: __init__ rather than __new__ (see timedelta), without pickle support:
    # Pystachy has no bytes. The fields are required, as _datetime's are.
    def __init__(self, year: int, month: int, day: int) -> None:
        """Constructor.

        Arguments:

        year, month, day (required, base 1)
        """
        year, month, day = _check_date_fields(year, month, day)
        self._year = year
        self._month = month
        self._day = day
        self._hashcode = -1

    # Additional constructors

    @classmethod
    def fromtimestamp(cls, t):
        "Construct a date from a POSIX timestamp (like time.time())."
        if t is None:
            raise TypeError("'NoneType' object cannot be interpreted as an integer")
        y, m, d, hh, mm, ss, weekday, jday, dst = _localtime(t)  # Pystachy port: (see there)
        return cls(y, m, d)

    @classmethod
    def today(cls):
        "Construct a date from time.time()."
        t = _time.time()
        return cls.fromtimestamp(t)

    @classmethod
    def fromordinal(cls, n: int):
        """Construct a date from a proleptic Gregorian ordinal.

        January 1 of year 1 is day 1.  Only the year, month and day are
        non-zero in the result.
        """
        if n < 1:
            raise ValueError("ordinal must be >= 1")  # Pystachy port: _datetime's check
        y, m, d = _ord2ymd(n)
        return cls(y, m, d)

    @classmethod
    def fromisoformat(cls, date_string: str):
        """Construct a date from a string in ISO 8601 format."""
        if not isinstance(date_string, str):
            raise TypeError('fromisoformat: argument must be str')

        if len(date_string) not in (7, 8, 10):
            raise ValueError(f'Invalid isoformat string: {date_string!r}')

        # Pystachy port: _datetimemodule.c's parser (see _parse_isoformat_date()); the
        # constructor reports the fields' errors, as _datetime's does
        rv, year, month, day = _parse_isoformat_date(date_string, len(date_string))
        if rv < 0:
            raise ValueError(f'Invalid isoformat string: {date_string!r}')
        return cls(year, month, day)

    @classmethod
    def fromisocalendar(cls, year: int, week: int, day: int):
        """Construct a date from the ISO year, week number and weekday.

        This is the inverse of the date.isocalendar() function"""
        y, m, d = _isoweek_to_gregorian(year, week, day)  # Pystachy port: (see fromisoformat)
        return cls(y, m, d)

    # Conversions to string

    def __repr__(self):
        """Convert to formal string, for repr().

        >>> d = date(2010, 1, 1)
        >>> repr(d)
        'datetime.date(2010, 1, 1)'
        """
        return "%s.%s(%d, %d, %d)" % (_get_class_module(self),
                                      "date",  # Pystachy port: (no __class__)
                                      self._year,
                                      self._month,
                                      self._day)
    # XXX These shouldn't depend on time.localtime(), because that
    # clips the usable dates to [1970 .. 2038).  At least ctime() is
    # easily done without using strftime() -- that's better too because
    # strftime("%c", ...) is locale specific.


    def ctime(self):
        "Return ctime() style string."
        weekday = self.toordinal() % 7 or 7
        return "%s %s %2d 00:00:00 %04d" % (
            _DAYNAMES[weekday],
            _MONTHNAMES[self._month],
            self._day, self._year)

    def strftime(self, format: str) -> str:
        """
        Format using strftime().

        Example: "%d/%m/%Y, %H:%M:%S"
        """
        return _wrap_strftime(self, format, self.timetuple())

    def __format__(self, fmt):
        if not isinstance(fmt, str):
            raise TypeError("must be str, not %s" % _type_name(fmt))  # Pystachy port: no type()
        if len(fmt) != 0:
            return self.strftime(fmt)
        return str(self)

    def isoformat(self) -> str:
        """Return the date formatted according to ISO.

        This is 'YYYY-MM-DD'.

        References:
        - https://www.w3.org/TR/NOTE-datetime
        - https://www.cl.cam.ac.uk/~mgk25/iso-time.html
        """
        return "%04d-%02d-%02d" % (self._year, self._month, self._day)

    def __str__(self):  # Pystachy port: a method, for __str__ = isoformat
        return self.isoformat()

    # Read-only field accessors
    @property
    def year(self) -> int:  # Pystachy port: a property needs its return annotation
        """year (1-9999)"""
        return self._year

    @property
    def month(self) -> int:  # Pystachy port: (see year)
        """month (1-12)"""
        return self._month

    @property
    def day(self) -> int:  # Pystachy port: (see year)
        """day (1-31)"""
        return self._day

    # Standard conversions, __eq__, __le__, __lt__, __ge__, __gt__,
    # __hash__ (and helpers)

    def timetuple(self) -> _struct_time:
        "Return local time tuple compatible with time.localtime()."
        return _build_struct_time(self._year, self._month, self._day,
                                  0, 0, 0, -1)

    def toordinal(self) -> int:
        """Return proleptic Gregorian ordinal for the year, month and day.

        January 1 of year 1 is day 1.  Only the year, month and day values
        contribute to the result.
        """
        return _ymd2ord(self._year, self._month, self._day)

    def replace(self, year=None, month=None, day=None):
        """Return a new date with new values for the specified fields."""
        if year is None:
            year = self._year
        if month is None:
            month = self._month
        if day is None:
            day = self._day
        return date(year, month, day)  # Pystachy port: date, as Pystachy has no type(self)

    # Pystachy port: __replace__ = replace is left out: copy.replace() is not available, and
    # a class-body alias of a method is not supported

    # Comparisons of date objects with other.

    # Pystachy port: NotImplemented is not supported (see timedelta.__add__). A datetime is
    # not equal to a date, and is not ordered with one, as in CPython.
    def __eq__(self, other: 'date') -> bool:
        if isinstance(other, date) and not isinstance(other, datetime):
            return self._cmp(other) == 0
        return False

    def __le__(self, other: 'date') -> bool:
        if isinstance(other, date) and not isinstance(other, datetime):
            return self._cmp(other) <= 0
        raise _not_ordered("<=", self, other)

    def __lt__(self, other: 'date') -> bool:
        if isinstance(other, date) and not isinstance(other, datetime):
            return self._cmp(other) < 0
        raise _not_ordered("<", self, other)

    def __ge__(self, other: 'date') -> bool:
        if isinstance(other, date) and not isinstance(other, datetime):
            return self._cmp(other) >= 0
        raise _not_ordered(">=", self, other)

    def __gt__(self, other: 'date') -> bool:
        if isinstance(other, date) and not isinstance(other, datetime):
            return self._cmp(other) > 0
        raise _not_ordered(">", self, other)

    def _cmp(self, other: 'date') -> int:
        assert isinstance(other, date)
        assert not isinstance(other, datetime)
        y, m, d = self._year, self._month, self._day
        y2, m2, d2 = other._year, other._month, other._day
        return _cmp((y, m, d), (y2, m2, d2))

    def __hash__(self) -> int:  # Pystachy port: annotated
        "Hash."
        if self._hashcode == -1:
            # Pystachy port: the hash of the fields that _getstate() packs into bytes
            self._hashcode = hash((self._year, self._month, self._day))
        return self._hashcode

    # Computations

    def __add__(self, other: timedelta) -> 'date':
        "Add a date to a timedelta."
        if isinstance(other, timedelta):
            o = self.toordinal() + other.days
            if 0 < o <= _MAXORDINAL:
                return date.fromordinal(o)  # Pystachy port: (see replace())
            raise OverflowError("date value out of range")  # Pystachy port: _datetime's
        raise _unsupported("+", self, other)

    def __radd__(self, other: timedelta) -> 'date':  # Pystachy port: (see timedelta)
        return self.__add__(other)

    def __sub__(self, other):
        """Subtract two dates, or a date and a timedelta."""
        if isinstance(other, timedelta):
            return self + timedelta(-other.days)
        # Pystachy port: _datetime's date - datetime is not supported
        if isinstance(other, date) and not isinstance(other, datetime):
            days1 = self.toordinal()
            days2 = other.toordinal()
            return timedelta(days1 - days2)
        raise _unsupported("-", self, other)

    def weekday(self) -> int:
        "Return day of the week, where Monday == 0 ... Sunday == 6."
        return (self.toordinal() + 6) % 7

    # Day-of-the-week and week-of-the-year, according to ISO

    def isoweekday(self) -> int:
        "Return day of the week, where Monday == 1 ... Sunday == 7."
        # 1-Jan-0001 is a Monday
        return self.toordinal() % 7 or 7

    def isocalendar(self) -> '_IsoCalendarDate':
        """Return a named tuple containing ISO year, week number, and weekday.

        The first ISO week of the year is the (Mon-Sun) week
        containing the year's first Thursday; everything else derives
        from that.

        The first week is 1; Monday is 1 ... Sunday is 7.

        ISO calendar algorithm taken from
        https://www.phys.uu.nl/~vgent/calendar/isocalendar.htm
        (used with permission)
        """
        year = self._year
        week1monday = _isoweek1monday(year)
        today = _ymd2ord(self._year, self._month, self._day)
        # Internally, week and day have origin 0
        week, day = divmod(today - week1monday, 7)
        if week < 0:
            year -= 1
            week1monday = _isoweek1monday(year)
            week, day = divmod(today - week1monday, 7)
        elif week >= 52:
            if today >= _isoweek1monday(year+1):
                year += 1
                week = 0
        return _IsoCalendarDate(year, week+1, day+1)

    # Pystachy port: pickle support is left out, as Pystachy has no bytes or pickle module


_date_class = date  # so functions w/ args named "date" can get at the class

date.min = date(1, 1, 1)
date.max = date(9999, 12, 31)
date.resolution = timedelta(days=1)


class tzinfo:
    """Abstract base class for time zone info classes.

    Subclasses must override the tzname(), utcoffset() and dst() methods.
    """
    __slots__ = ()

    # Pystachy port: the methods are annotated: the time's or datetime's methods call the
    # subclass's (a time passes None as dt)
    def tzname(self, dt: 'datetime') -> 'str | None':
        "datetime -> string name of time zone."
        raise NotImplementedError("tzinfo subclass must override tzname()")

    def utcoffset(self, dt: 'datetime') -> 'timedelta | None':
        "datetime -> timedelta, positive for east of UTC, negative for west of UTC"
        raise NotImplementedError("tzinfo subclass must override utcoffset()")

    def dst(self, dt: 'datetime') -> 'timedelta | None':
        """datetime -> DST offset as timedelta, positive for east of UTC.

        Return 0 if DST not in effect.  utcoffset() must include the DST
        offset.
        """
        raise NotImplementedError("tzinfo subclass must override dst()")

    def fromutc(self, dt: 'datetime') -> 'datetime':
        "datetime in UTC -> datetime in local time."

        if not isinstance(dt, datetime):
            raise TypeError("fromutc() requires a datetime argument")
        if dt.tzinfo is not self:
            raise ValueError("dt.tzinfo is not self")

        dtoff = dt.utcoffset()
        if dtoff is None:
            raise ValueError("fromutc() requires a non-None utcoffset() "
                             "result")

        # See the long comment block at the end of this file for an
        # explanation of this algorithm.
        dtdst = dt.dst()
        if dtdst is None:
            raise ValueError("fromutc() requires a non-None dst() result")
        delta = dtoff - dtdst
        if delta:
            dt += delta
            dtdst = dt.dst()
            if dtdst is None:
                raise ValueError("fromutc(): dt.dst gave inconsistent "
                                 "results; cannot convert")
        return dt + dtdst

    # Pystachy port: pickle support is left out, as Pystachy has no bytes or pickle module


# Pystachy port: a NamedTuple, as Pystachy has no tuple subclasses (nor __new__), named
# _IsoCalendarDate rather than deleted (a class cannot be); its repr is _datetime's
class _IsoCalendarDate(NamedTuple):
    year: int
    week: int
    weekday: int

    def __repr__(self) -> str:
        return (f'datetime.IsoCalendarDate'
                f'(year={self[0]}, week={self[1]}, weekday={self[2]})')


_tzinfo_class = tzinfo

class time:
    """Time with time zone.

    Constructors:

    __new__()

    Operators:

    __repr__, __str__
    __eq__, __le__, __lt__, __ge__, __gt__, __hash__

    Methods:

    strftime()
    isoformat()
    utcoffset()
    tzname()
    dst()

    Properties (readonly):
    hour, minute, second, microsecond, tzinfo, fold
    """
    __slots__ = '_hour', '_minute', '_second', '_microsecond', '_tzinfo', '_hashcode', '_fold'
    # Pystachy port: the class attributes assigned after the class are declared here
    min: 'time | None' = None
    max: 'time | None' = None
    resolution: 'timedelta | None' = None

    # Pystachy port: __init__ rather than __new__, without pickle support (see date)
    def __init__(self, hour: int = 0, minute: int = 0, second: int = 0,
                 microsecond: int = 0, tzinfo: '_tzinfo_class | None' = None, *,
                 fold: int = 0) -> None:
        """Constructor.

        Arguments:

        hour, minute (required)
        second, microsecond (default to zero)
        tzinfo (default to None)
        fold (keyword only, default to zero)
        """
        hour, minute, second, microsecond, fold = _check_time_fields(
            hour, minute, second, microsecond, fold)
        _check_tzinfo_arg(tzinfo)
        self._hour = hour
        self._minute = minute
        self._second = second
        self._microsecond = microsecond
        self._tzinfo = tzinfo
        self._hashcode = -1
        self._fold = fold

    # Read-only field accessors
    @property
    def hour(self) -> int:  # Pystachy port: a property needs its return annotation
        """hour (0-23)"""
        return self._hour

    @property
    def minute(self) -> int:  # Pystachy port: (see hour)
        """minute (0-59)"""
        return self._minute

    @property
    def second(self) -> int:  # Pystachy port: (see hour)
        """second (0-59)"""
        return self._second

    @property
    def microsecond(self) -> int:  # Pystachy port: (see hour)
        """microsecond (0-999999)"""
        return self._microsecond

    @property
    def tzinfo(self) -> '_tzinfo_class | None':  # Pystachy port: (see hour)
        """timezone info object"""
        return self._tzinfo

    @property
    def fold(self) -> int:  # Pystachy port: (see hour)
        return self._fold

    # Standard conversions, __hash__ (and helpers)

    # Comparisons of time objects with other.

    # Pystachy port: NotImplemented is not supported (see timedelta.__add__)
    def __eq__(self, other: 'time') -> bool:
        if isinstance(other, time):
            return self._cmp(other, allow_mixed=True) == 0
        else:
            return False

    def __le__(self, other: 'time') -> bool:
        if isinstance(other, time):
            return self._cmp(other) <= 0
        else:
            raise _not_ordered("<=", self, other)

    def __lt__(self, other: 'time') -> bool:
        if isinstance(other, time):
            return self._cmp(other) < 0
        else:
            raise _not_ordered("<", self, other)

    def __ge__(self, other: 'time') -> bool:
        if isinstance(other, time):
            return self._cmp(other) >= 0
        else:
            raise _not_ordered(">=", self, other)

    def __gt__(self, other: 'time') -> bool:
        if isinstance(other, time):
            return self._cmp(other) > 0
        else:
            raise _not_ordered(">", self, other)

    def _cmp(self, other: 'time', allow_mixed: bool = False) -> int:
        assert isinstance(other, time)
        mytz = self._tzinfo
        ottz = other._tzinfo
        myoff: timedelta | None = None
        otoff: timedelta | None = None

        if mytz is ottz:
            base_compare = True
        else:
            myoff = self.utcoffset()
            otoff = other.utcoffset()
            base_compare = _offsets_equal(myoff, otoff)  # Pystachy port: (see there)

        if base_compare:
            return _cmp((self._hour, self._minute, self._second,
                         self._microsecond),
                        (other._hour, other._minute, other._second,
                         other._microsecond))
        if myoff is None or otoff is None:
            if allow_mixed:
                return 2 # arbitrary non-zero value
            else:
                raise TypeError("can't compare offset-naive and offset-aware times")
        # Pystachy port: time_richcompare() of _datetimemodule.c, which compares the times'
        # seconds less the offsets' seconds (_pydatetime rounds the offsets to minutes)
        myss = (self._hour * 3600 + self._minute * 60 + self._second -
                myoff.days * 86400 - myoff.seconds)
        otss = (other._hour * 3600 + other._minute * 60 + other._second -
                otoff.days * 86400 - otoff.seconds)
        return _cmp((myss, self._microsecond), (otss, other._microsecond))

    def __hash__(self) -> int:  # Pystachy port: annotated
        """Hash."""
        if self._hashcode == -1:
            if self.fold:
                t = self.replace(fold=0)
            else:
                t = self
            tzoff = t.utcoffset()
            if not tzoff:  # zero or None
                # Pystachy port: the hash of the fields that _getstate() packs into bytes
                self._hashcode = hash((t._hour, t._minute, t._second, t._microsecond))
            else:
                h, m = divmod(timedelta(hours=self.hour, minutes=self.minute) - tzoff,
                              timedelta(hours=1))
                assert not m % timedelta(minutes=1), "whole minute"
                mm = m // timedelta(minutes=1)  # Pystachy port: for m //= ... (m is a timedelta)
                if 0 <= h < 24:
                    self._hashcode = hash(time(h, mm, self.second, self.microsecond))
                else:
                    self._hashcode = hash((h, mm, self.second, self.microsecond))
        return self._hashcode

    # Conversion to string

    def _tzstr(self):
        """Return formatted timezone offset (+xx:xx) or an empty string."""
        off = self.utcoffset()
        return _format_offset(off)

    def __repr__(self):
        """Convert to formal string, for repr()."""
        if self._microsecond != 0:
            s = ", %d, %d" % (self._second, self._microsecond)
        elif self._second != 0:
            s = ", %d" % self._second
        else:
            s = ""
        s= "%s.%s(%d, %d%s)" % (_get_class_module(self),
                                "time",  # Pystachy port: (no __class__)
                                self._hour, self._minute, s)
        if self._tzinfo is not None:
            assert s[-1:] == ")"
            s = s[:-1] + ", tzinfo=%r" % self._tzinfo + ")"
        if self._fold:
            assert s[-1:] == ")"
            s = s[:-1] + ", fold=1)"
        return s

    def isoformat(self, timespec='auto'):
        """Return the time formatted according to ISO.

        The full format is 'HH:MM:SS.mmmmmm+zz:zz'. By default, the fractional
        part is omitted if self.microsecond == 0.

        The optional argument timespec specifies the number of additional
        terms of the time to include. Valid options are 'auto', 'hours',
        'minutes', 'seconds', 'milliseconds' and 'microseconds'.
        """
        s = _format_time(self._hour, self._minute, self._second,
                          self._microsecond, timespec)
        tz = self._tzstr()
        if tz:
            s += tz
        return s

    def __str__(self):  # Pystachy port: a method, for __str__ = isoformat
        return self.isoformat()

    @classmethod
    def fromisoformat(cls, time_string: str):
        """Construct a time from a string in one of the ISO 8601 formats."""
        if not isinstance(time_string, str):
            raise TypeError('fromisoformat: argument must be str')

        # The spec actually requires that time-only ISO 8601 strings start with
        # T, but the extended format allows this to be omitted as long as there
        # is no ambiguity with date strings.
        # Pystachy port: _datetimemodule.c's parser (see _parse_isoformat_date()); the
        # message shows the string with its T, as _datetime's does
        p = 1 if _c_at(time_string, 0) == 'T' else 0
        rv, hour, minute, second, microsecond, tzoffset, tzus = _parse_isoformat_time(
            time_string, p)
        if rv < 0:
            raise ValueError(f'Invalid isoformat string: {time_string!r}')
        return cls(hour, minute, second, microsecond,
                   _tzinfo_from_isoformat(rv, tzoffset, tzus))

    def strftime(self, format: str) -> str:
        """Format using strftime().  The date part of the timestamp passed
        to underlying strftime should not be used.
        """
        # The year must be >= 1000 else Python's strftime implementation
        # can raise a bogus exception.
        timetuple = _struct_time(1900, 1, 1,  # Pystachy port: (see _struct_time)
                                 self._hour, self._minute, self._second,
                                 0, 1, -1)
        return _wrap_strftime(self, format, timetuple)

    def __format__(self, fmt):
        if not isinstance(fmt, str):
            raise TypeError("must be str, not %s" % _type_name(fmt))  # Pystachy port: no type()
        if len(fmt) != 0:
            return self.strftime(fmt)
        return str(self)

    # Timezone functions

    def utcoffset(self) -> 'timedelta | None':
        """Return the timezone offset as timedelta, positive east of UTC
         (negative west of UTC)."""
        if self._tzinfo is None:
            return None
        offset = self._tzinfo.utcoffset(None)
        _check_utc_offset("utcoffset", offset)
        return offset

    def tzname(self) -> 'str | None':
        """Return the timezone name.

        Note that the name is 100% informational -- there's no requirement that
        it mean anything in particular. For example, "GMT", "UTC", "-500",
        "-5:00", "EDT", "US/Eastern", "America/New York" are all valid replies.
        """
        if self._tzinfo is None:
            return None
        name = self._tzinfo.tzname(None)
        _check_tzname(name)
        return name

    def dst(self) -> 'timedelta | None':
        """Return 0 if DST is not in effect, or the DST offset (as timedelta
        positive eastward) if DST is in effect.

        This is purely informational; the DST offset has already been added to
        the UTC offset returned by utcoffset() if applicable, so there's no
        need to consult dst() unless you're interested in displaying the DST
        info.
        """
        if self._tzinfo is None:
            return None
        offset = self._tzinfo.dst(None)
        _check_utc_offset("dst", offset)
        return offset

    def replace(self, hour=None, minute=None, second=None, microsecond=None,
                tzinfo=True, *, fold=None):
        """Return a new time with new values for the specified fields."""
        if hour is None:
            hour = self.hour
        if minute is None:
            minute = self.minute
        if second is None:
            second = self.second
        if microsecond is None:
            microsecond = self.microsecond
        if fold is None:
            fold = self._fold
        # Pystachy port: tzinfo=True keeps the time zone; tzinfo cannot be assigned it, as a
        # variable has one type. The result is a time, as Pystachy has no type(self).
        if isinstance(tzinfo, bool):
            if tzinfo:
                return time(hour, minute, second, microsecond, self.tzinfo, fold=fold)
            raise TypeError("tzinfo argument must be None or of a tzinfo subclass")
        else:
            return time(hour, minute, second, microsecond, tzinfo, fold=fold)

    # Pystachy port: __replace__ = replace is left out: copy.replace() is not available, and
    # a class-body alias of a method is not supported

    # Pystachy port: pickle support is left out, as Pystachy has no bytes or pickle module


_time_class = time  # so functions w/ args named "time" can get at the class

time.min = time(0, 0, 0)
time.max = time(23, 59, 59, 999999)
time.resolution = timedelta(microseconds=1)

# Pystachy port: myoff == otoff for two offsets that may be None, as the C code compares
# them: None is equal only to None
def _offsets_equal(a: 'timedelta | None', b: 'timedelta | None') -> bool:
    if a is None or b is None:
        return a is None and b is None
    return a == b


class datetime(date):
    """datetime(year, month, day[, hour[, minute[, second[, microsecond[,tzinfo]]]]])

    The year, month and day arguments are required. tzinfo may be None, or an
    instance of a tzinfo subclass. The remaining arguments may be ints.
    """
    # Pystachy port: time.__slots__ but '_hashcode', which date declares (the slots must be
    # literal and not repeat inherited ones)
    __slots__ = '_hour', '_minute', '_second', '_microsecond', '_tzinfo', '_fold'
    # Pystachy port: the class attributes assigned after the class are declared here, with the
    # types of date's (a subclass cannot change them): datetime.min and datetime.max are
    # datetimes, but typed date
    min: 'date | None' = None
    max: 'date | None' = None
    resolution: 'timedelta | None' = None

    # Pystachy port: __init__ rather than __new__, without pickle support (see date)
    def __init__(self, year: int, month: int, day: int, hour: int = 0, minute: int = 0,
                 second: int = 0, microsecond: int = 0,
                 tzinfo: '_tzinfo_class | None' = None, *, fold: int = 0) -> None:
        year, month, day = _check_date_fields(year, month, day)
        hour, minute, second, microsecond, fold = _check_time_fields(
            hour, minute, second, microsecond, fold)
        _check_tzinfo_arg(tzinfo)
        self._year = year
        self._month = month
        self._day = day
        self._hour = hour
        self._minute = minute
        self._second = second
        self._microsecond = microsecond
        self._tzinfo = tzinfo
        self._hashcode = -1
        self._fold = fold

    # Read-only field accessors
    @property
    def hour(self) -> int:  # Pystachy port: a property needs its return annotation
        """hour (0-23)"""
        return self._hour

    @property
    def minute(self) -> int:  # Pystachy port: (see hour)
        """minute (0-59)"""
        return self._minute

    @property
    def second(self) -> int:  # Pystachy port: (see hour)
        """second (0-59)"""
        return self._second

    @property
    def microsecond(self) -> int:  # Pystachy port: (see hour)
        """microsecond (0-999999)"""
        return self._microsecond

    @property
    def tzinfo(self) -> '_tzinfo_class | None':  # Pystachy port: (see hour)
        """timezone info object"""
        return self._tzinfo

    @property
    def fold(self) -> int:  # Pystachy port: (see hour)
        return self._fold

    @classmethod
    def _fromtimestamp(cls, t, utc: bool, tz: '_tzinfo_class | None'):
        """Construct a datetime from a POSIX timestamp (like time.time()).

        A timezone info object may be passed in as well.
        """
        # Pystachy port: _PyTime_ObjectToTimeval() of CPython, which datetime_from_timestamp()
        # calls, rejects NaN and timestamps beyond time_t's range
        if isinstance(t, float):
            if t != t:
                raise ValueError("Invalid value NaN (not a number)")
            frac, ft = _math.modf(t)
            us = round(frac * 1e6)
            if us >= 1000000:
                ft += 1
                us -= 1000000
            elif us < 0:
                ft -= 1
                us += 1000000
            if not -9.223372036854776e18 <= ft < 9.223372036854776e18:
                raise OverflowError("timestamp out of range for platform time_t")
            it = int(ft)
        else:
            us = 0
            it = t

        # Pystachy port: the time module has no gmtime() or localtime(): _gmtime() computes
        # the UTC fields, and local time is not supported (see _localtime())
        if utc:
            y, m, d, hh, mm, ss = _gmtime(it)
        else:
            y, m, d, hh, mm, ss, weekday, jday, dst = _localtime(it)
        ss = min(ss, 59)    # clamp out leap seconds if the platform has them
        result = cls(y, m, d, hh, mm, ss, us, tz)
        if tz is not None:
            result = tz.fromutc(result)
        return result

    @classmethod
    def fromtimestamp(cls, timestamp, tz: '_tzinfo_class | None' = None):
        """Construct a datetime from a POSIX timestamp (like time.time()).

        A timezone info object may be passed in as well.
        """
        _check_tzinfo_arg(tz)

        return cls._fromtimestamp(timestamp, tz is not None, tz)

    @classmethod
    def utcfromtimestamp(cls, t):
        """Construct a naive UTC datetime from a POSIX timestamp."""
        import warnings
        warnings.warn("datetime.datetime.utcfromtimestamp() is deprecated and scheduled "
                      "for removal in a future version. Use timezone-aware "
                      "objects to represent datetimes in UTC: "
                      "datetime.datetime.fromtimestamp(t, datetime.UTC).",
                      DeprecationWarning,
                      stacklevel=2)
        return cls._fromtimestamp(t, True, None)

    @classmethod
    def now(cls, tz: '_tzinfo_class | None' = None):
        "Construct a datetime from time.time() and optional time zone info."
        t = _time.time()
        return cls.fromtimestamp(t, tz)

    @classmethod
    def utcnow(cls):
        "Construct a UTC datetime from time.time()."
        import warnings
        warnings.warn("datetime.datetime.utcnow() is deprecated and scheduled for "
                      "removal in a future version. Use timezone-aware "
                      "objects to represent datetimes in UTC: "
                      "datetime.datetime.now(datetime.UTC).",
                      DeprecationWarning,
                      stacklevel=2)
        t = _time.time()
        return cls._fromtimestamp(t, True, None)

    @classmethod
    def combine(cls, date: '_date_class', time: '_time_class', tzinfo=True):
        "Construct a datetime from a given date and a given time."
        if not isinstance(date, _date_class):
            raise TypeError("date argument must be a date instance")
        if not isinstance(time, _time_class):
            raise TypeError("time argument must be a time instance")
        # Pystachy port: tzinfo=True keeps the time's time zone (see time.replace())
        if isinstance(tzinfo, bool):
            if tzinfo:
                return cls(date.year, date.month, date.day,
                           time.hour, time.minute, time.second, time.microsecond,
                           time.tzinfo, fold=time.fold)
            raise TypeError("tzinfo argument must be None or of a tzinfo subclass")
        else:
            return cls(date.year, date.month, date.day,
                       time.hour, time.minute, time.second, time.microsecond,
                       tzinfo, fold=time.fold)

    @classmethod
    def fromisoformat(cls, date_string: str):
        """Construct a datetime from a string in one of the ISO 8601 formats."""
        if not isinstance(date_string, str):
            raise TypeError('fromisoformat: argument must be str')

        if len(date_string) < 7:
            raise ValueError(f'Invalid isoformat string: {date_string!r}')

        # Pystachy port: _datetimemodule.c's parser (see _parse_isoformat_date()), which reads
        # the time after the separator character; the constructor reports the fields' errors
        try:
            separator_location = _find_isoformat_datetime_separator(date_string)
        except ValueError:
            raise ValueError(
                f'Invalid isoformat string: {date_string!r}') from None
        rv, year, month, day = _parse_isoformat_date(date_string, separator_location)
        hour = minute = second = microsecond = tzoffset = tzus = 0
        if rv == 0 and len(date_string) > separator_location:
            rv, hour, minute, second, microsecond, tzoffset, tzus = _parse_isoformat_time(
                date_string, separator_location + 1)
        if rv < 0:
            raise ValueError(f'Invalid isoformat string: {date_string!r}')
        return cls(year, month, day, hour, minute, second, microsecond,
                   _tzinfo_from_isoformat(rv, tzoffset, tzus))

    def timetuple(self) -> _struct_time:
        "Return local time tuple compatible with time.localtime()."
        dst = self.dst()
        # Pystachy port: the flag is a new variable, as one variable has one type
        if dst is None:
            flag = -1
        elif dst:
            flag = 1
        else:
            flag = 0
        return _build_struct_time(self.year, self.month, self.day,
                                  self.hour, self.minute, self.second,
                                  flag)

    def _mktime(self):
        """Return integer POSIX timestamp."""
        # Pystachy port: the conversion of local times needs time.localtime() (see _localtime())
        return _localtime_seconds(self)


    def timestamp(self):
        "Return POSIX timestamp as float"
        if self._tzinfo is None:
            s = self._mktime()
            return s + self.microsecond / 1e6
        else:
            return (self - _EPOCH).total_seconds()

    def utctimetuple(self) -> _struct_time:
        "Return UTC time tuple compatible with time.gmtime()."
        offset = self.utcoffset()
        # Pystachy port: a new variable for self - offset
        utc = self
        if offset:
            utc = self - offset
        y, m, d = utc.year, utc.month, utc.day
        hh, mm, ss = utc.hour, utc.minute, utc.second
        return _build_struct_time(y, m, d, hh, mm, ss, 0)

    def date(self) -> '_date_class':
        "Return the date part."
        return date(self._year, self._month, self._day)

    def time(self) -> '_time_class':
        "Return the time part, with tzinfo None."
        return time(self.hour, self.minute, self.second, self.microsecond, fold=self.fold)

    def timetz(self) -> '_time_class':
        "Return the time part, with same tzinfo."
        return time(self.hour, self.minute, self.second, self.microsecond,
                    self._tzinfo, fold=self.fold)

    def replace(self, year=None, month=None, day=None, hour=None,
                minute=None, second=None, microsecond=None, tzinfo=True,
                *, fold=None):
        """Return a new datetime with new values for the specified fields."""
        if year is None:
            year = self.year
        if month is None:
            month = self.month
        if day is None:
            day = self.day
        if hour is None:
            hour = self.hour
        if minute is None:
            minute = self.minute
        if second is None:
            second = self.second
        if microsecond is None:
            microsecond = self.microsecond
        if fold is None:
            fold = self.fold
        # Pystachy port: (see time.replace())
        if isinstance(tzinfo, bool):
            if tzinfo:
                return datetime(year, month, day, hour, minute, second,
                                microsecond, self.tzinfo, fold=fold)
            raise TypeError("tzinfo argument must be None or of a tzinfo subclass")
        else:
            return datetime(year, month, day, hour, minute, second,
                            microsecond, tzinfo, fold=fold)

    # Pystachy port: __replace__ = replace is left out: copy.replace() is not available, and
    # a class-body alias of a method is not supported

    def _local_timezone(self):
        # Pystachy port: the local time zone needs time.localtime() (see _localtime())
        return _local_timezone_of(self)

    def astimezone(self, tz: '_tzinfo_class | None' = None) -> 'datetime':
        if tz is None:
            tz = self._local_timezone()
        elif not isinstance(tz, tzinfo):
            raise TypeError("tz argument must be an instance of tzinfo")

        mytz = self.tzinfo
        if mytz is None:
            mytz = self._local_timezone()
            myoffset = mytz.utcoffset(self)
        else:
            myoffset = mytz.utcoffset(self)
            if myoffset is None:
                mytz = self.replace(tzinfo=None)._local_timezone()
                myoffset = mytz.utcoffset(self)

        if tz is mytz:
            return self

        # Convert self to UTC, and attach the new time zone object.
        utc = (self - myoffset).replace(tzinfo=tz)

        # Convert from UTC to tz's local time.
        return tz.fromutc(utc)

    # Ways to produce a string.

    def ctime(self):
        "Return ctime() style string."
        weekday = self.toordinal() % 7 or 7
        return "%s %s %2d %02d:%02d:%02d %04d" % (
            _DAYNAMES[weekday],
            _MONTHNAMES[self._month],
            self._day,
            self._hour, self._minute, self._second,
            self._year)

    def isoformat(self, sep='T', timespec='auto'):
        """Return the time formatted according to ISO.

        The full format looks like 'YYYY-MM-DD HH:MM:SS.mmmmmm'.
        By default, the fractional part is omitted if self.microsecond == 0.

        If self.tzinfo is not None, the UTC offset is also attached, giving
        a full format of 'YYYY-MM-DD HH:MM:SS.mmmmmm+HH:MM'.

        Optional argument sep specifies the separator between date and
        time, default 'T'.

        The optional argument timespec specifies the number of additional
        terms of the time to include. Valid options are 'auto', 'hours',
        'minutes', 'seconds', 'milliseconds' and 'microseconds'.
        """
        s = ("%04d-%02d-%02d%c" % (self._year, self._month, self._day, sep) +
             _format_time(self._hour, self._minute, self._second,
                          self._microsecond, timespec))

        off = self.utcoffset()
        tz = _format_offset(off)
        if tz:
            s += tz

        return s

    def __repr__(self):
        """Convert to formal string, for repr()."""
        L = [self._year, self._month, self._day,  # These are never zero
             self._hour, self._minute, self._second, self._microsecond]
        if L[-1] == 0:
            del L[-1]
        if L[-1] == 0:
            del L[-1]
        s = "%s.%s(%s)" % (_get_class_module(self),
                           "datetime",  # Pystachy port: (no __class__)
                           ", ".join(map(str, L)))
        # Pystachy port: _datetime's repr has the fold before the time zone
        if self._fold:
            assert s[-1:] == ")"
            s = s[:-1] + ", fold=1)"
        if self._tzinfo is not None:
            assert s[-1:] == ")"
            s = s[:-1] + ", tzinfo=%r" % self._tzinfo + ")"
        return s

    def __str__(self):
        "Convert to string, for str()."
        return self.isoformat(sep=' ')

    @classmethod
    def strptime(cls, date_string, format):
        'string, format -> new datetime parsed from a string (like time.strptime()).'
        import _strptime
        return _strptime._strptime_datetime(cls, date_string, format)

    def utcoffset(self) -> 'timedelta | None':
        """Return the timezone offset as timedelta positive east of UTC (negative west of
        UTC)."""
        if self._tzinfo is None:
            return None
        offset = self._tzinfo.utcoffset(self)
        _check_utc_offset("utcoffset", offset)
        return offset

    def tzname(self) -> 'str | None':
        """Return the timezone name.

        Note that the name is 100% informational -- there's no requirement that
        it mean anything in particular. For example, "GMT", "UTC", "-500",
        "-5:00", "EDT", "US/Eastern", "America/New York" are all valid replies.
        """
        if self._tzinfo is None:
            return None
        name = self._tzinfo.tzname(self)
        _check_tzname(name)
        return name

    def dst(self) -> 'timedelta | None':
        """Return 0 if DST is not in effect, or the DST offset (as timedelta
        positive eastward) if DST is in effect.

        This is purely informational; the DST offset has already been added to
        the UTC offset returned by utcoffset() if applicable, so there's no
        need to consult dst() unless you're interested in displaying the DST
        info.
        """
        if self._tzinfo is None:
            return None
        offset = self._tzinfo.dst(self)
        _check_utc_offset("dst", offset)
        return offset

    # Comparisons of datetime objects with other.

    # Pystachy port: NotImplemented is not supported (see date.__eq__)
    def __eq__(self, other: '_date_class') -> bool:
        if isinstance(other, datetime):
            return self._cmp(other, allow_mixed=True) == 0
        else:
            return False

    def __le__(self, other: '_date_class') -> bool:
        if isinstance(other, datetime):
            return self._cmp(other) <= 0
        else:
            raise _not_ordered("<=", self, other)

    def __lt__(self, other: '_date_class') -> bool:
        if isinstance(other, datetime):
            return self._cmp(other) < 0
        else:
            raise _not_ordered("<", self, other)

    def __ge__(self, other: '_date_class') -> bool:
        if isinstance(other, datetime):
            return self._cmp(other) >= 0
        else:
            raise _not_ordered(">=", self, other)

    def __gt__(self, other: '_date_class') -> bool:
        if isinstance(other, datetime):
            return self._cmp(other) > 0
        else:
            raise _not_ordered(">", self, other)

    def _cmp(self, other: '_date_class', allow_mixed: bool = False) -> int:
        assert isinstance(other, datetime)
        mytz = self._tzinfo
        ottz = other._tzinfo
        myoff: timedelta | None = None
        otoff: timedelta | None = None

        if mytz is ottz:
            base_compare = True
        else:
            myoff = self.utcoffset()
            otoff = other.utcoffset()
            # Assume that allow_mixed means that we are called from __eq__
            if allow_mixed:
                # Pystachy port: 1 - fold rather than not fold, a bool, for the int field
                if not _offsets_equal(myoff, self.replace(fold=1 - self.fold).utcoffset()):
                    return 2
                if not _offsets_equal(otoff, other.replace(fold=1 - other.fold).utcoffset()):
                    return 2
            base_compare = _offsets_equal(myoff, otoff)  # Pystachy port: (see there)

        if base_compare:
            return _cmp((self._year, self._month, self._day,
                         self._hour, self._minute, self._second,
                         self._microsecond),
                        (other._year, other._month, other._day,
                         other._hour, other._minute, other._second,
                         other._microsecond))
        if myoff is None or otoff is None:
            if allow_mixed:
                return 2 # arbitrary non-zero value
            else:
                raise TypeError("can't compare offset-naive and offset-aware datetimes")
        # XXX What follows could be done more efficiently...
        diff = self - other     # this will take offsets into account
        if diff.days < 0:
            return -1
        return 1 if diff else 0  # Pystachy port: diff and 1 or 0 would join a timedelta

    def __add__(self, other: timedelta) -> 'datetime':
        "Add a datetime and a timedelta."
        if not isinstance(other, timedelta):
            raise _unsupported("+", self, other)  # Pystachy port: (see timedelta.__add__)
        delta = timedelta(self.toordinal(),
                          hours=self._hour,
                          minutes=self._minute,
                          seconds=self._second,
                          microseconds=self._microsecond)
        delta += other
        hour, rem = divmod(delta.seconds, 3600)
        minute, second = divmod(rem, 60)
        if 0 < delta.days <= _MAXORDINAL:
            # Pystachy port: datetime and date, as Pystachy has no type(self)
            return datetime.combine(date.fromordinal(delta.days),
                                    time(hour, minute, second,
                                         delta.microseconds,
                                         tzinfo=self._tzinfo))
        raise OverflowError("date value out of range")  # Pystachy port: _datetime's

    def __radd__(self, other: timedelta) -> 'datetime':  # Pystachy port: (see timedelta)
        return self.__add__(other)

    def __sub__(self, other):
        "Subtract two datetimes, or a datetime and a timedelta."
        if not isinstance(other, datetime):
            if isinstance(other, timedelta):
                return self + -other
            raise _unsupported("-", self, other)  # Pystachy port: (see timedelta.__add__)

        days1 = self.toordinal()
        days2 = other.toordinal()
        secs1 = self._second + self._minute * 60 + self._hour * 3600
        secs2 = other._second + other._minute * 60 + other._hour * 3600
        base = timedelta(days1 - days2,
                         secs1 - secs2,
                         self._microsecond - other._microsecond)
        if self._tzinfo is other._tzinfo:
            return base
        myoff = self.utcoffset()
        otoff = other.utcoffset()
        # Pystachy port: (see _offsets_equal()), and _datetime's message
        if _offsets_equal(myoff, otoff):
            return base
        if myoff is None or otoff is None:
            raise TypeError("can't subtract offset-naive and offset-aware datetimes")
        return base + otoff - myoff

    def __hash__(self) -> int:  # Pystachy port: annotated
        if self._hashcode == -1:
            if self.fold:
                t = self.replace(fold=0)
            else:
                t = self
            tzoff = t.utcoffset()
            if tzoff is None:
                # Pystachy port: the hash of the fields that _getstate() packs into bytes
                self._hashcode = hash((t._year, t._month, t._day, t._hour, t._minute, t._second, t._microsecond))
            else:
                days = _ymd2ord(self.year, self.month, self.day)
                seconds = self.hour * 3600 + self.minute * 60 + self.second
                self._hashcode = hash(timedelta(days, seconds, self.microsecond) - tzoff)
        return self._hashcode

    # Pystachy port: pickle support is left out, as Pystachy has no bytes or pickle module


datetime.min = datetime(1, 1, 1)
datetime.max = datetime(9999, 12, 31, 23, 59, 59, 999999)
datetime.resolution = timedelta(microseconds=1)


def _isoweek1monday(year):
    # Helper to calculate the day number of the Monday starting week 1
    THURSDAY = 3
    firstday = _ymd2ord(year, 1, 1)
    firstweekday = (firstday + 6) % 7  # See weekday() above
    week1monday = firstday - firstweekday
    if firstweekday > THURSDAY:
        week1monday += 7
    return week1monday


class timezone(tzinfo):
    __slots__ = '_offset', '_name'
    # Pystachy port: the class attributes assigned after the class are declared here
    utc: 'timezone | None' = None
    min: 'timezone | None' = None
    max: 'timezone | None' = None

    # Pystachy port: __init__ rather than __new__ (see timedelta). An omitted name is None
    # rather than the _Omitted sentinel, and timezone(timedelta(0)) is a new object equal
    # to timezone.utc, rather than timezone.utc itself.
    def __init__(self, offset: timedelta, name: str | None = None) -> None:
        if not isinstance(offset, timedelta):
            raise TypeError("timezone() argument 1 must be datetime.timedelta, not None")
        # Pystachy port: _datetime's message, with the offset's repr
        if not timezone._minoffset <= offset <= timezone._maxoffset:
            raise ValueError("offset must be a timedelta "
                             "strictly between -timedelta(hours=24) and "
                             "timedelta(hours=24), not %r." % offset)
        self._offset = offset
        self._name = name

    def __init_subclass__(cls):
        raise TypeError("type 'datetime.timezone' is not an acceptable base type")

    @classmethod
    def _create(cls, offset, name=None):
        return cls(offset, name)  # Pystachy port: (see __init__)

    def __getinitargs__(self):
        """pickle support"""
        if self._name is None:
            return (self._offset,)
        return (self._offset, self._name)

    def __eq__(self, other: 'timezone') -> bool:
        if isinstance(other, timezone):
            return self._offset == other._offset
        return False  # Pystachy port: (see timedelta.__eq__)

    def __hash__(self) -> int:  # Pystachy port: annotated
        return hash(self._offset)

    def __repr__(self):
        """Convert to formal string, for repr().

        >>> tz = timezone.utc
        >>> repr(tz)
        'datetime.timezone.utc'
        >>> tz = timezone(timedelta(hours=-5), 'EST')
        >>> repr(tz)
        "datetime.timezone(datetime.timedelta(-1, 68400), 'EST')"
        """
        # Pystachy port: timezone.utc is the time zone of offset 0 without a name (see
        # __init__)
        if self._name is None and not self._offset:
            return 'datetime.timezone.utc'
        if self._name is None:
            return "%s.%s(%r)" % (_get_class_module(self),
                                  "timezone",  # Pystachy port: (no __class__)
                                  self._offset)
        return "%s.%s(%r, %r)" % (_get_class_module(self),
                                  "timezone",
                                  self._offset, self._name)

    def __str__(self):
        return self.tzname(None)

    def utcoffset(self, dt: 'datetime') -> 'timedelta | None':
        if isinstance(dt, datetime) or dt is None:
            return self._offset
        raise TypeError("utcoffset() argument must be a datetime instance"
                        " or None")

    def tzname(self, dt: 'datetime') -> str:
        if isinstance(dt, datetime) or dt is None:
            name = self._name  # Pystachy port: a local, which the test narrows
            if name is None:
                return self._name_from_offset(self._offset)
            return name
        raise TypeError("tzname() argument must be a datetime instance"
                        " or None")

    def dst(self, dt: 'datetime') -> 'timedelta | None':
        if isinstance(dt, datetime) or dt is None:
            return None
        raise TypeError("dst() argument must be a datetime instance"
                        " or None")

    def fromutc(self, dt: 'datetime') -> 'datetime':
        if isinstance(dt, datetime):
            if dt.tzinfo is not self:
                raise ValueError("fromutc: dt.tzinfo "
                                 "is not self")
            return dt + self._offset
        raise TypeError("fromutc() argument must be a datetime instance"
                        " or None")

    _maxoffset = timedelta(hours=24, microseconds=-1)
    # Pystachy port: a class body cannot read its own names, and the type is annotated
    _minoffset: timedelta = -timedelta(hours=24, microseconds=-1)

    @staticmethod
    def _name_from_offset(delta: timedelta) -> str:
        if not delta:
            return 'UTC'
        if delta < timedelta(0):
            sign = '-'
            delta = -delta
        else:
            sign = '+'
        # Pystachy port: the seconds are split (see _format_offset())
        minutes, seconds = divmod(delta.seconds, 60)
        hours, minutes = divmod(minutes, 60)
        microseconds = delta.microseconds
        if microseconds:
            return (f'UTC{sign}{hours:02d}:{minutes:02d}:{seconds:02d}'
                    f'.{microseconds:06d}')
        if seconds:
            return f'UTC{sign}{hours:02d}:{minutes:02d}:{seconds:02d}'
        return f'UTC{sign}{hours:02d}:{minutes:02d}'

UTC = timezone.utc = timezone._create(timedelta(0))

# bpo-37642: These attributes are rounded to the nearest minute for backwards
# compatibility, even though the constructor will accept a wider range of
# values. This may change in the future.
timezone.min = timezone._create(-timedelta(hours=23, minutes=59))
timezone.max = timezone._create(timedelta(hours=23, minutes=59))
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

# Pystachy port: Pystachy's time module has no localtime() or mktime(), so the local time
# zone is unknown: the operations that need it raise NotImplementedError when they run
# (CPython converts with the local time zone). gmtime() is _gmtime() below.
def _localtime(t) -> tuple[int, int, int, int, int, int, int, int, int]:
    raise NotImplementedError("datetime: local time is not supported "
                              "(Pystachy's time module has no localtime())")

def _localtime_seconds(dt: datetime) -> int:
    raise NotImplementedError("datetime: local time is not supported "
                              "(Pystachy's time module has no mktime())")

def _local_timezone_of(dt: datetime) -> timezone:
    raise NotImplementedError("datetime: local time is not supported "
                              "(Pystachy's time module has no localtime())")

def _gmtime(t: int) -> tuple[int, int, int, int, int, int]:
    # time.gmtime(t)'s year, month, day, hour, minute and second
    days, secs = divmod(t, 86400)
    y, m, d = _ord2ymd(days + 719163)  # (719163 is date(1970, 1, 1).toordinal())
    if not -2147481748 <= y <= 2147485547:
        # (glibc's gmtime_r() fails where tm_year would overflow an int)
        raise OSError(75, "Value too large for defined data type")
    hh, secs = divmod(secs, 3600)
    mm, ss = divmod(secs, 60)
    return y, m, d, hh, mm, ss

# Some time zone algebra.  For a datetime x, let
#     x.n = x stripped of its timezone -- its naive time.
#     x.o = x.utcoffset(), and assuming that doesn't raise an exception or
#           return None
#     x.d = x.dst(), and assuming that doesn't raise an exception or
#           return None
#     x.s = x's standard offset, x.o - x.d
#
# Now some derived rules, where k is a duration (timedelta).
#
# 1. x.o = x.s + x.d
#    This follows from the definition of x.s.
#
# 2. If x and y have the same tzinfo member, x.s = y.s.
#    This is actually a requirement, an assumption we need to make about
#    sane tzinfo classes.
#
# 3. The naive UTC time corresponding to x is x.n - x.o.
#    This is again a requirement for a sane tzinfo class.
#
# 4. (x+k).s = x.s
#    This follows from #2, and that datetime.timetz+timedelta preserves tzinfo.
#
# 5. (x+k).n = x.n + k
#    Again follows from how arithmetic is defined.
#
# Now we can explain tz.fromutc(x).  Let's assume it's an interesting case
# (meaning that the various tzinfo methods exist, and don't blow up or return
# None when called).
#
# The function wants to return a datetime y with timezone tz, equivalent to x.
# x is already in UTC.
#
# By #3, we want
#
#     y.n - y.o = x.n                             [1]
#
# The algorithm starts by attaching tz to x.n, and calling that y.  So
# x.n = y.n at the start.  Then it wants to add a duration k to y, so that [1]
# becomes true; in effect, we want to solve [2] for k:
#
#    (y+k).n - (y+k).o = x.n                      [2]
#
# By #1, this is the same as
#
#    (y+k).n - ((y+k).s + (y+k).d) = x.n          [3]
#
# By #5, (y+k).n = y.n + k, which equals x.n + k because x.n=y.n at the start.
# Substituting that into [3],
#
#    x.n + k - (y+k).s - (y+k).d = x.n; the x.n terms cancel, leaving
#    k - (y+k).s - (y+k).d = 0; rearranging,
#    k = (y+k).s - (y+k).d; by #4, (y+k).s == y.s, so
#    k = y.s - (y+k).d
#
# On the RHS, (y+k).d can't be computed directly, but y.s can be, and we
# approximate k by ignoring the (y+k).d term at first.  Note that k can't be
# very large, since all offset-returning methods return a duration of magnitude
# less than 24 hours.  For that reason, if y is firmly in std time, (y+k).d must
# be 0, so ignoring it has no consequence then.
#
# In any case, the new value is
#
#     z = y + y.s                                 [4]
#
# It's helpful to step back at look at [4] from a higher level:  it's simply
# mapping from UTC to tz's standard time.
#
# At this point, if
#
#     z.n - z.o = x.n                             [5]
#
# we have an equivalent time, and are almost done.  The insecurity here is
# at the start of daylight time.  Picture US Eastern for concreteness.  The wall
# time jumps from 1:59 to 3:00, and wall hours of the form 2:MM don't make good
# sense then.  The docs ask that an Eastern tzinfo class consider such a time to
# be EDT (because it's "after 2"), which is a redundant spelling of 1:MM EST
# on the day DST starts.  We want to return the 1:MM EST spelling because that's
# the only spelling that makes sense on the local wall clock.
#
# In fact, if [5] holds at this point, we do have the standard-time spelling,
# but that takes a bit of proof.  We first prove a stronger result.  What's the
# difference between the LHS and RHS of [5]?  Let
#
#     diff = x.n - (z.n - z.o)                    [6]
#
# Now
#     z.n =                       by [4]
#     (y + y.s).n =               by #5
#     y.n + y.s =                 since y.n = x.n
#     x.n + y.s =                 since z and y are have the same tzinfo member,
#                                     y.s = z.s by #2
#     x.n + z.s
#
# Plugging that back into [6] gives
#
#     diff =
#     x.n - ((x.n + z.s) - z.o) =     expanding
#     x.n - x.n - z.s + z.o =         cancelling
#     - z.s + z.o =                   by #2
#     z.d
#
# So diff = z.d.
#
# If [5] is true now, diff = 0, so z.d = 0 too, and we have the standard-time
# spelling we wanted in the endcase described above.  We're done.  Contrarily,
# if z.d = 0, then we have a UTC equivalent, and are also done.
#
# If [5] is not true now, diff = z.d != 0, and z.d is the offset we need to
# add to z (in effect, z is in tz's standard time, and we need to shift the
# local clock into tz's daylight time).
#
# Let
#
#     z' = z + z.d = z + diff                     [7]
#
# and we can again ask whether
#
#     z'.n - z'.o = x.n                           [8]
#
# If so, we're done.  If not, the tzinfo class is insane, according to the
# assumptions we've made.  This also requires a bit of proof.  As before, let's
# compute the difference between the LHS and RHS of [8] (and skipping some of
# the justifications for the kinds of substitutions we've done several times
# already):
#
#     diff' = x.n - (z'.n - z'.o) =           replacing z'.n via [7]
#             x.n  - (z.n + diff - z'.o) =    replacing diff via [6]
#             x.n - (z.n + x.n - (z.n - z.o) - z'.o) =
#             x.n - z.n - x.n + z.n - z.o + z'.o =    cancel x.n
#             - z.n + z.n - z.o + z'.o =              cancel z.n
#             - z.o + z'.o =                      #1 twice
#             -z.s - z.d + z'.s + z'.d =          z and z' have same tzinfo
#             z'.d - z.d
#
# So z' is UTC-equivalent to x iff z'.d = z.d at this point.  If they are equal,
# we've found the UTC-equivalent so are done.  In fact, we stop with [7] and
# return z', not bothering to compute z'.d.
#
# How could z.d and z'd differ?  z' = z + z.d [7], so merely moving z' by
# a dst() offset, and starting *from* a time already in DST (we know z.d != 0),
# would have to change the result dst() returns:  we start in DST, and moving
# a little further into it takes us out of DST.
#
# There isn't a sane case where this can happen.  The closest it gets is at
# the end of DST, where there's an hour in UTC with no spelling in a hybrid
# tzinfo class.  In US Eastern, that's 5:MM UTC = 0:MM EST = 1:MM EDT.  During
# that hour, on an Eastern clock 1:MM is taken as being in standard time (6:MM
# UTC) because the docs insist on that, but 0:MM is taken as being in daylight
# time (4:MM UTC).  There is no local time mapping to 5:MM UTC.  The local
# clock jumps from 1:59 back to 1:00 again, and repeats the 1:MM hour in
# standard time.  Since that's what the local clock *does*, we want to map both
# UTC hours 5:MM and 6:MM to 1:MM Eastern.  The result is ambiguous
# in local time, but so it goes -- it's the way the local clock works.
#
# When x = 5:MM UTC is the input to this algorithm, x.o=0, y.o=-5 and y.d=0,
# so z=0:MM.  z.d=60 (minutes) then, so [5] doesn't hold and we keep going.
# z' = z + z.d = 1:MM then, and z'.d=0, and z'.d - z.d = -60 != 0 so [8]
# (correctly) concludes that z' is not UTC-equivalent to x.
#
# Because we know z.d said z was in daylight time (else [5] would have held and
# we would have stopped then), and we know z.d != z'.d (else [8] would have held
# and we have stopped then), and there are only 2 possible values dst() can
# return in Eastern, it follows that z'.d must be 0 (which it is in the example,
# but the reasoning doesn't depend on the example -- it depends on there being
# two possible dst() outcomes, one zero and the other non-zero).  Therefore
# z' must be in standard time, and is the spelling we want in this case.
#
# Note again that z' is not UTC-equivalent as far as the hybrid tzinfo class is
# concerned (because it takes z' as being in standard time rather than the
# daylight time we intend here), but returning it gives the real-life "local
# clock repeats an hour" behavior when mapping the "unspellable" UTC hour into
# tz.
#
# When the input is 6:MM, z=1:MM and z.d=0, and we stop at once, again with
# the 1:MM standard time spelling we want.
#
# So how can this break?  One of the assumptions must be violated.  Two
# possibilities:
#
# 1) [2] effectively says that y.s is invariant across all y belong to a given
#    time zone.  This isn't true if, for political reasons or continental drift,
#    a region decides to change its base offset from UTC.
#
# 2) There may be versions of "double daylight" time where the tail end of
#    the analysis gives up a step too early.  I haven't thought about that
#    enough to say.
#
# In any case, it's clear that the default fromutc() is strong enough to handle
# "almost all" time zones:  so long as the standard offset is invariant, it
# doesn't matter if daylight time transition points change from year to year, or
# if daylight time is skipped in some years; it doesn't matter how large or
# small dst() may get within its bounds; and it doesn't even matter if some
# perverse time zone returns a negative dst()).  So a breaking case must be
# pretty bizarre, and a tzinfo subclass can override fromutc() if it is.
