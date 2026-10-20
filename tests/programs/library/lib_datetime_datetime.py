# lib/datetime.py's datetime: construction checks, combine(), fromisoformat() as
# _datetimemodule.c parses it, isoformat() with separators and timespecs, arithmetic and its
# range, naive and aware subtraction and comparisons, timestamps and fromtimestamp() in UTC
# and fixed offsets, astimezone() between fixed offsets, time tuples, strftime() with %f, %z,
# %:z and %Z, a DST tzinfo subclass through tzinfo.fromutc(), and now() with a time zone.
from datetime import UTC, date, datetime, time, timedelta, timezone, tzinfo
from typing import Callable


def show(label: str, f: Callable[[], str]) -> None:
    try:
        print(label, f())
    except (ValueError, OverflowError, TypeError, OSError) as e:
        print(label, type(e).__name__ + ":", e)


est = timezone(timedelta(hours=-5), "EST")
ist = timezone(timedelta(hours=5, minutes=30))
print(datetime.min, datetime.max, datetime.resolution, repr(datetime.min), repr(datetime.max))
for args in [(2024, 2, 29, 0, 0, 0, 0), (2023, 2, 29, 0, 0, 0, 0), (2024, 13, 1, 0, 0, 0, 0),
             (0, 1, 1, 0, 0, 0, 0), (2024, 1, 1, 24, 0, 0, 0), (2024, 1, 1, 0, 60, 0, 0),
             (2024, 1, 1, 0, 0, 60, 0), (2024, 1, 1, 0, 0, 0, 1000000),
             (9999, 12, 31, 23, 59, 59, 999999), (1, 1, 1, 0, 0, 0, 1)]:
    show("datetime%r" % (args,), lambda: repr(datetime(*args)))
show("fold=2", lambda: repr(datetime(2024, 1, 1, fold=2)))

d1 = datetime(2024, 2, 29, 13, 5, 7, 25000, tzinfo=ist, fold=1)
print(repr(d1), str(d1), d1.year, d1.month, d1.day, d1.hour, d1.minute, d1.second,
      d1.microsecond, d1.tzinfo, d1.fold)
print(d1.date(), repr(d1.time()), repr(d1.timetz()), d1.toordinal(), d1.weekday(),
      d1.isoweekday(), d1.isocalendar(), d1.ctime())
for spec in ["auto", "hours", "minutes", "seconds", "milliseconds", "microseconds", "x"]:
    show(spec, lambda: d1.isoformat(timespec=spec) + " " + d1.isoformat(" ", spec) + " " +
         datetime(2024, 1, 1).isoformat("_", spec))
print(d1.isoformat("é"), datetime(1, 1, 1).isoformat("T"), f"{d1}", f"{d1:%d/%m/%Y %H:%M}")
print(d1.timetuple(), d1.utctimetuple(), datetime(2024, 1, 1).utctimetuple())
print(repr(datetime.combine(date(2020, 5, 17), time(1, 2, 3, tzinfo=est))),
      repr(datetime.combine(date(2020, 5, 17), time(1, 2, 3, tzinfo=est), None)),
      repr(datetime.combine(date(2020, 5, 17), time(1, 2, fold=1), UTC)),
      repr(datetime.combine(d1, d1.timetz())))

# ISO strings: any separator, the date forms of date.fromisoformat() and time offsets.
for s in ["2024-02-29T13:05:07", "2024-02-29 13:05:07.5+05:30", "20240229T130507Z", "2024-02-29",
          "2024-W09-4T12", "2024W094T12:00", "2024-W09T12", "2024W09T12", "2024-02-29T",
          "2024-02-29X12:30", "2024-02-2912:30", "2024-02-29T25:00", "2024-02-30T12:00",
          "2024-02-29T12:00+24:00", "2024-02-29T12:00-23:59:59.999999", "2024-02-29T12:30:45.",
          "2024-02-29T1230", "2024-02-29 12:30:45,123456789", "2024", "2024-02", "2024-W01-",
          "2024-W1", "", "0001-01-01T00:00:00", "9999-12-31T23:59:59.999999",
          "2024-02-29T12:00Z00", "2024-02-29T12:00z", "2024-02-29T12:00 ", "2024-02-29T12é"]:
    show("fromisoformat(%r)" % s, lambda: repr(datetime.fromisoformat(s)))

# Arithmetic.
d2 = datetime(2023, 12, 31, 23, 59, 59, 999999)
for td in [timedelta(microseconds=1), timedelta(days=-365), timedelta(hours=-24, seconds=1),
           timedelta(weeks=52, microseconds=-1), timedelta(days=3652058)]:
    show("d2 + %r" % td, lambda: repr(d2 + td) + " " + repr(d2 - td))
show("max + 1us", lambda: repr(datetime.max + timedelta(microseconds=1)))
show("min - 1us", lambda: repr(datetime.min - timedelta(microseconds=1)))
show("aware max + 1", lambda: repr(datetime(9999, 12, 31, tzinfo=est) + timedelta(1)))
print(d2 - datetime(2023, 1, 1), datetime(2023, 1, 1) - d2, datetime.max - datetime.min)
a1 = datetime(2024, 1, 1, 12, tzinfo=UTC)
a2 = datetime(2024, 1, 1, 7, tzinfo=est)
a3 = datetime(2024, 1, 1, 17, 30, tzinfo=ist)
print(a1 - a2, a3 - a2, a2 - a3, a1 - datetime(2024, 1, 1, 12, tzinfo=timezone(timedelta(0))))
show("naive - aware", lambda: str(d2 - a1))
show("aware - naive", lambda: str(a1 - d2))

# Comparisons: aware ones in UTC, naive and aware never equal.
dts = [a1, a2, a3, datetime(2024, 1, 1, 12), datetime(2024, 1, 1, 12, 0, 0, 1, tzinfo=UTC)]
for x in dts:
    print([x == y for y in dts], [x != y for y in dts])
for x in dts[:3]:
    print([x < y for y in dts[:3] + [dts[4]]], [x >= y for y in dts[:3] + [dts[4]]])
show("naive < aware", lambda: str(dts[3] < a1))
show("aware >= naive", lambda: str(a1 >= dts[3]))
print(sorted([d2, datetime(2024, 1, 1), datetime(2000, 2, 29, 1)]), max(dts[:3]), min(dts[:3]))

# Timestamps: aware datetimes, and fromtimestamp() with a time zone.
print(a1.timestamp(), a2.timestamp(), datetime(1, 1, 1, tzinfo=UTC).timestamp(),
      datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=est).timestamp())
stamps: list[int | float] = [0, 1700000000, -1, 1e9 + 0.5, 1.0000005, -0.5, -1e-7, 1e-7,
                             253402300799.999999, -62135596800, -62135596801, 253402300800, 1e20,
                             -1e13, float("nan"), 2 ** 62, 0.1234565, 1234567890.9999995,
                             -1234567890.0000005, 9.3e18, -9.3e18, 1e17]
for ts in stamps:
    show("fromtimestamp(%r)" % ts, lambda: repr(datetime.fromtimestamp(ts, UTC)) + " " +
         repr(datetime.fromtimestamp(ts, tz=est)))
for tz in [UTC, est, ist]:
    t0 = datetime(2024, 3, 10, 6, 59, 59, 999999, tzinfo=tz)
    print(repr(datetime.fromtimestamp(t0.timestamp(), tz)), repr(t0.astimezone(UTC)),
          repr(t0.astimezone(est)), repr(t0.astimezone(tz)))
show("astimezone(max)", lambda: repr(datetime(1, 1, 1, tzinfo=ist).astimezone(UTC)))

# strftime() replacements and glibc's directives.
for x in [d1, d2, a2, datetime(1, 1, 1), datetime(1, 2, 3, 4, 5, 6, 7, tzinfo=timezone(
          timedelta(hours=-3, seconds=-7, microseconds=-8), "odd%name"))]:
    print(repr(x.strftime("%Y-%m-%d %H:%M:%S.%f %z %:z %Z %%z %c %j %U %G-%V-%u|%E")))


# A tzinfo with US-style daylight time: tzinfo.fromutc() and the fold rules.
class Eastern(tzinfo):
    def utcoffset(self, dt: datetime | None) -> timedelta:
        return timedelta(hours=-5) + self.dst(dt)

    def dst(self, dt: datetime | None) -> timedelta:
        if dt is None:
            return timedelta(0)
        start = datetime(dt.year, 3, 8, 2) + timedelta(days=6 - datetime(dt.year, 3, 8).weekday())
        end = datetime(dt.year, 11, 1, 1) + timedelta(days=6 - datetime(dt.year, 11, 1).weekday())
        naive = dt.replace(tzinfo=None)
        if start <= naive < end:
            return timedelta(hours=1)
        return timedelta(0)

    def tzname(self, dt: datetime | None) -> str:
        return "EDT" if self.dst(dt) else "EST"

    def __repr__(self) -> str:
        return "Eastern()"


eastern = Eastern()
for u in [datetime(2024, 3, 10, 6, 59), datetime(2024, 3, 10, 7, 0), datetime(2024, 11, 3, 5, 30),
          datetime(2024, 11, 3, 6, 30), datetime(2024, 7, 4, 16)]:
    loc = u.replace(tzinfo=UTC).astimezone(eastern)
    print(repr(loc), loc.tzname(), loc.dst(), loc.utcoffset(), loc.isoformat(),
          loc.strftime("%Z %z"), loc.timetuple().tm_isdst, loc.astimezone(UTC))
w1 = datetime(2024, 11, 3, 1, 30, tzinfo=eastern)
w2 = datetime(2024, 11, 3, 1, 30, tzinfo=eastern, fold=1)
print(w1 == w2, w1 - w2, w1.utcoffset(), w2.utcoffset(), w1 == w1.astimezone(UTC))

# now() with a time zone is consistent with time.time() through the same conversions.
n = datetime.now(UTC)
print(n.tzinfo is UTC, n.year >= 2024, (datetime.now(UTC) - n) < timedelta(seconds=30),
      datetime.now(est).utcoffset(), datetime.now(timezone.utc).tzname())
