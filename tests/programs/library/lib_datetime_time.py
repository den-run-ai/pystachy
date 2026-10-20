# lib/datetime.py's time and timezone: construction checks, isoformat() with each timespec,
# fromisoformat() as _datetimemodule.c parses it, repr() and str(), comparisons of naive and
# aware times (offsets with seconds included), utcoffset(), tzname() and dst(), replace(),
# strftime(), the timezone class (names, ranges and its constants), and a tzinfo subclass.
from datetime import UTC, datetime, time, timedelta, timezone, tzinfo
from typing import Callable


def show(label: str, f: Callable[[], str]) -> None:
    try:
        print(label, f())
    except (ValueError, OverflowError, TypeError) as e:
        print(label, type(e).__name__ + ":", e)


print(time.min, time.max, time.resolution, repr(time.min), repr(time.max), repr(time()))
for h, m, sec, us in [(0, 0, 0, 0), (23, 59, 59, 999999), (24, 0, 0, 0), (-1, 0, 0, 0),
                      (0, 60, 0, 0), (0, 0, 60, 0), (0, 0, 0, 1000000), (0, 0, 0, -1),
                      (12, 5, 0, 7)]:
    show("time%r" % ((h, m, sec, us),), lambda: repr(time(h, m, sec, us)))
show("fold=2", lambda: repr(time(fold=2)))
show("fold=-1", lambda: repr(time(1, fold=-1)))

t = time(9, 5, 3, 25000)
for spec in ["auto", "hours", "minutes", "seconds", "milliseconds", "microseconds", "nanos", ""]:
    show("isoformat(%r)" % spec, lambda: t.isoformat(spec) + " " + time(9, 5).isoformat(spec))
print(t, repr(t), t.hour, t.minute, t.second, t.microsecond, t.tzinfo, t.fold, f"{t}",
      f"{t:%H.%M.%S.%f}", t.utcoffset(), t.tzname(), t.dst())

# The C parser: optional T, HH[:MM[:SS[.ffffff]]] (separators all or none), fractions of
# any length, offsets (Z, +HH, +HHMM, +HH:MM:SS.ffffff); its quirks are CPython's.
for s in ["12", "1230", "12:30", "123045", "12:30:45", "12:30:45.5", "12:30:45,123", "T12:30",
          "12:30:45.1234567", "12:30:45.000001", "12:30+05", "12:30-0530", "12:30+05:30:15",
          "12:30+05:30:15.5", "12:30Z", "12:30z", "12:30Z00", "00:00+00:00", "00:00-00:00",
          "23:59:59.999999+23:59:59.999999", "00:00+24:00", "00:00-24:00", "24:00", "12:60",
          "12:3", "1", "", "T", "TT12", "12:30:", "12:30.", "12:30:45.", "12:30.5", "1230:45",
          "12:3045", "20200101", "12:30:45:123", "123045123", "12:30+", "12:30+5", "12:30+053",
          "12:30 ", " 12:30", "12:30é", "１２:30", "12:30+05:30garbage", "12\x0030"]:
    show("fromisoformat(%r)" % s, lambda: repr(time.fromisoformat(s)))

# Time zones.
est = timezone(timedelta(hours=-5), "EST")
ist = timezone(timedelta(hours=5, minutes=30))
odd = timezone(timedelta(seconds=-30, microseconds=-5))
zones = [UTC, timezone.utc, timezone(timedelta(0)), timezone(timedelta(0), "UTC"), est, ist, odd,
         timezone(timedelta(hours=23, minutes=59, seconds=59, microseconds=999999)),
         timezone.min, timezone.max, timezone(timedelta(seconds=1), "naïve ±")]
for z in zones:
    print(repr(z), "|", str(z), "|", z.tzname(None), z.utcoffset(None), z.dst(None),
          z == UTC, z == est)
show("timezone(24h)", lambda: repr(timezone(timedelta(hours=24))))
show("timezone(-24h)", lambda: repr(timezone(timedelta(hours=-24))))
show("timezone(-24h+1us)", lambda: repr(timezone(timedelta(hours=-24, microseconds=1))))

aware = [time(12, 0, tzinfo=UTC), time(7, 0, tzinfo=est), time(17, 30, tzinfo=ist),
         time(12, 0, 0, 5, tzinfo=odd), time(11, 59, 30, 5, tzinfo=odd), time(12, 0)]
for a in aware:
    print(repr(a), str(a), a.utcoffset(), a.tzname(), a.dst(), a.isoformat("minutes"))
    print("  ", [a == b for b in aware], [a != b for b in aware])
for a in aware[:5]:
    print([a < b for b in aware[:5]], [a >= b for b in aware[:5]])
show("naive < aware", lambda: str(aware[5] < aware[0]))
show("aware > naive", lambda: str(aware[0] > aware[5]))

# replace().
ta = time(1, 2, 3, 4, tzinfo=est, fold=1)
print(repr(ta), repr(ta.replace(hour=5)), repr(ta.replace(tzinfo=None)), repr(ta.replace(fold=0)),
      repr(ta.replace(tzinfo=UTC, microsecond=0)), repr(ta.replace()))
show("replace(minute=60)", lambda: repr(ta.replace(minute=60)))

# strftime(): the date part is 1900-01-01.
for f in ["%H:%M:%S.%f", "%I %p %P", "%Y-%m-%d %j %a %A %U %W %V", "%z|%:z|%Z", "%c", "%X %x",
          "%-H|%_M|%3S|%^p|%#Z", "%%f %%z", "é %H ü"]:
    print(repr(ta.strftime(f)), repr(time(23, 59, 1, 9).strftime(f)))


# A tzinfo subclass: offsets and names from its methods.
class Fixed(tzinfo):
    def __init__(self, minutes: int, name: str) -> None:
        self.minutes = minutes
        self.name = name

    def utcoffset(self, dt: datetime | None) -> timedelta:
        return timedelta(minutes=self.minutes)

    def tzname(self, dt: datetime | None) -> str:
        return self.name

    def dst(self, dt: datetime | None) -> timedelta:
        return timedelta(0)

    def __repr__(self) -> str:
        return "Fixed(%d, %r)" % (self.minutes, self.name)


tf = time(10, 30, tzinfo=Fixed(90, "Zoné+1:30"))
print(repr(tf), str(tf), tf.utcoffset(), tf.tzname(), tf.dst(), tf.strftime("%Z %z %:z"))
print(tf == time(9, 0, tzinfo=UTC), tf < time(9, 1, tzinfo=UTC), tf > time(8, 59, tzinfo=UTC))
bad = time(1, tzinfo=Fixed(24 * 60, "day"))
show("utcoffset 24h", lambda: str(bad.utcoffset()))
show("isoformat 24h", lambda: bad.isoformat())
