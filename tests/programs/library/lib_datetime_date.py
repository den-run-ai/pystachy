# lib/datetime.py's date: construction checks with _datetime's messages, leap years,
# toordinal() and fromordinal() over the whole range, the ISO calendar, fromisoformat() and
# fromisocalendar(), isoformat(), ctime(), replace(), arithmetic with timedeltas and its range
# errors, comparisons, timetuple(), and strftime() with glibc's C-locale directives, flags and
# widths (non-ASCII text in formats included).
from datetime import MAXYEAR, MINYEAR, date, datetime, timedelta
from typing import Callable


def show(label: str, f: Callable[[], str]) -> None:
    try:
        print(label, f())
    except (ValueError, OverflowError, TypeError) as e:
        print(label, type(e).__name__ + ":", e)


print(MINYEAR, MAXYEAR, date.min, date.max, date.resolution, repr(date.min), repr(date.max))

# Construction.
for y, m, d in [(1, 1, 1), (9999, 12, 31), (0, 1, 1), (10000, 1, 1), (-5, 1, 1), (2020, 0, 1),
                (2020, 13, 1), (2020, 1, 0), (2020, 1, 32), (2020, 4, 31), (2021, 2, 29),
                (2020, 2, 30), (2020, 2, 29), (2020, 6, 30), (2020, 12, 31)]:
    show("date%r" % ((y, m, d),), lambda: repr(date(y, m, d)))

# Leap years: divisible by 4, but centuries only when divisible by 400.
for y in [1, 4, 100, 200, 300, 400, 1600, 1700, 1800, 1900, 2000, 2004, 2023, 2024, 2100, 2400,
          9996, 9999]:
    show("leap %d" % y, lambda: str(date(y, 2, 29)) + " " + str(date(y, 3, 1).toordinal() -
                                                                   date(y, 2, 28).toordinal()))

# toordinal() and fromordinal() agree over the range, with year, month and day sums.
total = 0
n = 0
o = 1
while o <= 3652059:
    dd = date.fromordinal(o)
    assert dd.toordinal() == o
    assert date(dd.year, dd.month, dd.day) == dd
    total += dd.year * 10000 + dd.month * 100 + dd.day
    n += 1
    o += 997
print(n, total, date.fromordinal(1), date.fromordinal(3652059), date.fromordinal(730120))
for o in [0, -1, 3652060]:
    show("fromordinal(%d)" % o, lambda: repr(date.fromordinal(o)))
print(date(2000, 1, 1).toordinal(), date(1970, 1, 1).toordinal(), date(1, 12, 31).toordinal())

# Weekdays and the ISO calendar around new year, including 53-week years.
for y in [1, 1999, 2004, 2009, 2015, 2020, 2021, 2026, 9998, 9999]:
    for start in [date(y, 12, 26), date(y, 1, 1)]:
        if start.year == 9999 and start.month == 12:
            start = date(9999, 12, 25)
        row = []
        for k in range(7):
            dd = start + timedelta(days=k)
            iy, iw, iwd = dd.isocalendar()
            row.append("%s:%d/%d/%d-%d-%d" % (dd.isoformat(), dd.weekday(), dd.isoweekday(),
                                              iy, iw, iwd))
        print(" ".join(row))
ic = date(2020, 12, 31).isocalendar()
print(ic, ic.year, ic.week, ic.weekday, ic[0], ic == (2020, 53, 4), len(ic))
for y, w, d in [(2020, 53, 7), (2021, 53, 1), (2015, 53, 1), (2004, 53, 5), (1, 1, 1),
                (9999, 52, 5), (9999, 52, 7), (0, 1, 1), (10000, 1, 1), (2020, 0, 1),
                (2020, 54, 1), (2020, 1, 0), (2020, 1, 8)]:
    show("fromisocalendar%r" % ((y, w, d),), lambda: repr(date.fromisocalendar(y, w, d)))

# ISO strings.
for s in ["2020-01-01", "20200101", "2020-W01", "2020W01", "2020-W01-3", "2020W013", "2020-W53-7",
          "2021-W53", "0001-01-01", "9999-12-31", "0000-01-01", "2020-1-01", "2020-13-01",
          "2020-02-30", "", "abcd-ef-gh", "2020-01-01T00", "2020-01", "202001", "2020-0101",
          "2020W01-3", "2020-W013", "２０２０-01-01", "2020-01-0١", "2020-01-1é"]:
    show("fromisoformat(%r)" % s, lambda: repr(date.fromisoformat(s)))

# Strings.
for dd in [date(1, 1, 1), date(999, 9, 9), date(2024, 2, 29), date(9999, 12, 31)]:
    print(str(dd), repr(dd), dd.isoformat(), dd.ctime(), f"{dd}", f"{dd:%d.%m.%Y}",
          format(dd, ""), dd.timetuple())

# replace().
d0 = date(2024, 2, 29)
print(d0.replace(), d0.replace(year=2028), d0.replace(month=3), d0.replace(day=1),
      d0.replace(2000, 1, 2))
show("replace(year=2023)", lambda: repr(d0.replace(year=2023)))
show("replace(month=13)", lambda: repr(d0.replace(month=13)))

# Arithmetic and its range.
print(d0 + timedelta(days=1), d0 + timedelta(days=366), d0 - timedelta(days=60),
      d0 + timedelta(hours=47, minutes=59), d0 - timedelta(seconds=1), d0 - date(2000, 1, 1),
      date(2000, 1, 1) - d0, date.max - date.min, date.min + (date.max - date.min))
show("max + 1", lambda: repr(date.max + timedelta(1)))
show("min - 1", lambda: repr(date.min - timedelta(1)))
show("min - 1us", lambda: repr(date.min - timedelta(microseconds=1)))
show("max + huge", lambda: repr(date.max + timedelta(days=-999999999)))

# Comparisons.
ds = [date(2020, 1, 1), date(2019, 12, 31), date(2020, 1, 1), date(1, 1, 1), date(9999, 1, 1)]
for a in ds:
    print([a < b for b in ds], [a == b for b in ds], [a != b for b in ds], [a >= b for b in ds])
print(sorted(ds), max(ds), min(ds))
dt = datetime(2020, 1, 1)
print(ds[0] == dt, ds[0] != dt, dt == ds[0])
show("datetime < date", lambda: str(dt < ds[0]))
show("date - datetime", lambda: str(ds[0] - dt))

# strftime(): glibc's directives in the C locale.
fmts = ["%a %A %b %B %h %c", "%C %d %D %e %F %g %G %j", "%H %I %k %l %M %p %P %r %R %S %T",
        "%u %U %V %w %W %x %X %y %Y", "%n%t%%", "%f|%z|%:z|%Z", "%Q %q %v %1 %+ %E %O%", "%",
        "a%", "%-d %-m %-j %_d %_m %05d %010Y %3C %-3e %_3e %03e", "%^a %^B %#a %#A %#b %#p %^p %#P",
        "%Ey %EY %EC %Ex %EX %Ec %Od %Oe %OH %Om %Oy %OB %Ob %Ed %EB %OY", "%10A|%-10a|%_8B|%08b",
        "%3%|%-3%|%_3%|%03%|%E%|%0E%|%5Z|%-5Z|%05Z|%3z|%-3z", "%12F|%-12F|%012D|%^9c", "%:%z %%z %:",
        "é%Y ü %d ✓ %ébB %%é", "x\x00%Y\x00y", "%2049Y|%1000d"]
for dd in [date(1, 1, 1), date(99, 12, 31), date(999, 6, 15), date(2024, 2, 29),
           date(2021, 1, 3), date(9999, 12, 31)]:
    for f in fmts:
        r = dd.strftime(f)
        print(repr(r) if len(r) < 120 else "%d %r %r" % (len(r), r[:20], r[-20:]))
