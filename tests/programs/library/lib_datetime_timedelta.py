# lib/datetime.py's timedelta (CPython 3.13's _pydatetime with marked edits that follow
# _datetimemodule.c): construction from each unit, with ints and floats and their rounding,
# normalization, str() and repr() of negative values, arithmetic with ints, floats and
# timedeltas, comparisons, total_seconds(), abs() and divmod(), the class constants, and
# CPython's errors; also in methods, closures and at module level.
from datetime import timedelta
from typing import Callable


def show(label: str, f: Callable[[], str]) -> None:
    try:
        print(label, f())
    except (ValueError, OverflowError, TypeError, ZeroDivisionError) as e:
        print(label, type(e).__name__ + ":", e)


# Each unit, normalized to days, seconds and microseconds.
print(repr(timedelta()), repr(timedelta(0)), timedelta(1), timedelta(0, 1), timedelta(0, 0, 1))
print(repr(timedelta(days=-1)), repr(timedelta(seconds=-1)), repr(timedelta(microseconds=-1)))
print(repr(timedelta(milliseconds=1500)), repr(timedelta(minutes=-90)), repr(timedelta(hours=25)))
print(repr(timedelta(weeks=3, days=-2, hours=1, minutes=1, seconds=1, milliseconds=1, microseconds=1)))
print(repr(timedelta(seconds=86400 * 3 + 5, microseconds=-10**6 * 7)))
print(repr(timedelta(microseconds=10**15)), repr(timedelta(milliseconds=-10**12)))

# str(): days with their plural, then H:MM:SS and microseconds when not 0.
for td in [timedelta(-1), timedelta(seconds=-1), timedelta(days=-1, seconds=86399),
           timedelta(days=2, hours=3), timedelta(days=-2, microseconds=5), timedelta(1),
           timedelta(microseconds=1), timedelta(hours=10, minutes=5, seconds=7),
           timedelta(days=999999999), timedelta(days=-999999999)]:
    print(str(td), "|", repr(td), "|", td.days, td.seconds, td.microseconds)

# Floats: the integral part exactly, the fractions of a microsecond rounded once, half to
# even on the total (as _datetimemodule.c's delta_new()).
floats = [timedelta(days=1.5), timedelta(seconds=0.5), timedelta(microseconds=0.5),
          timedelta(microseconds=1.5), timedelta(microseconds=2.5), timedelta(microseconds=-0.5),
          timedelta(microseconds=-1.5), timedelta(milliseconds=0.0005),
          timedelta(seconds=1e-6), timedelta(seconds=0.0000005), timedelta(seconds=1.0000005),
          timedelta(days=930.191872573572, weeks=427112), timedelta(hours=-6062419.121479347,
          weeks=-2335530.176939236, milliseconds=60.25), timedelta(minutes=0.1, seconds=0.1),
          timedelta(days=-27.9999995, microseconds=-166.73326236267758),
          timedelta(weeks=0.1, days=0.1, hours=0.1, minutes=0.1, seconds=0.1,
                    milliseconds=0.1, microseconds=0.1),
          timedelta(days=1e-9), timedelta(weeks=-1e-12), timedelta(microseconds=75.5, days=-782813)]
for td in floats:
    print(repr(td))

# A deterministic sweep of mixed int and float arguments.
seed = 12345


def lcg() -> int:
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return seed


for _ in range(60):
    a = lcg() % 2000000 - 1000000
    b = (lcg() % 2000001 - 1000000) / 997.0
    c = lcg() % 200000 - 100000
    d = (lcg() % 20001 - 10000) / 7.0
    print(repr(timedelta(days=a, seconds=b, microseconds=c, minutes=d)),
          repr(timedelta(hours=b, milliseconds=d, weeks=c / 100)))

# Range: |days| <= 999999999, with _datetime's messages.
show("max+", lambda: repr(timedelta(days=999999999, hours=24)))
show("days", lambda: repr(timedelta(days=1000000000)))
show("neg", lambda: repr(timedelta(days=-1000000000)))
show("float", lambda: repr(timedelta(days=1e9)))
show("C int", lambda: repr(timedelta(days=1e20)))
show("C int2", lambda: repr(timedelta(seconds=-1e300)))
show("nan", lambda: repr(timedelta(microseconds=float("nan"))))
show("inf", lambda: repr(timedelta(hours=float("inf"))))
show("-max", lambda: repr(-timedelta.max))
show("max*2", lambda: repr(timedelta.max * 2))
show("max+max", lambda: repr(timedelta.max + timedelta.max))
print(timedelta.min, "|", timedelta.max, "|", timedelta.resolution, "|", repr(-timedelta.min))

# Arithmetic.
t1 = timedelta(days=2, hours=5, microseconds=7)
t2 = timedelta(hours=-30, seconds=59)
print(t1 + t2, t1 - t2, t2 - t1, -t1, +t2, abs(t2), abs(t1))
print(t1 * 3, t1 * -2, t1 * 0, t2 * 10**6, t1 * True)
print(t1 * 0.5, t1 * 1.1, t1 * -0.1, t2 * 1e-6, t1 * 2.0 ** 20)
print(t1 / 3, t1 / -7, t2 / 1000000, t1 / 0.3, t2 / -2.5, t1 / 1e15, t1 / 2.0 ** 70)
print(t1 // 3, t2 // 7, t2 // -7, t1 // t2, t2 // t1, t1 / t2, t1 % t2, t2 % t1)
print(divmod(t1, t2), divmod(t2, timedelta(hours=1)), divmod(t1, timedelta(microseconds=3)))
print(timedelta(seconds=1) * 0.1, timedelta(seconds=1) / 3, timedelta(microseconds=3) / 2,
      timedelta(microseconds=5) / 2, timedelta(microseconds=-5) / 2, timedelta(1) / 7)
show("x/0", lambda: str(t1 / 0))
show("x//0", lambda: str(t1 // 0))
show("x/0.0", lambda: str(t1 / 0.0))
show("x/td0", lambda: str(t1 / timedelta(0)))
show("x//td0", lambda: str(t1 // timedelta(0)))
show("x%td0", lambda: str(t1 % timedelta(0)))
show("x*inf", lambda: str(t1 * float("inf")))
show("x*nan", lambda: str(t1 * float("nan")))
show("x/nan", lambda: str(t1 / float("nan")))
show("x*1e300", lambda: str(t1 * 1e300))
show("x/1e-300", lambda: str(t1 / 1e-300))

# Comparisons and truth.
ts = [timedelta(0), timedelta(microseconds=-1), timedelta(1), timedelta(hours=24),
      timedelta(days=-1, seconds=86399, microseconds=999999)]
for a1 in ts:
    print([a1 < b1 for b1 in ts], [a1 == b1 for b1 in ts], [a1 >= b1 for b1 in ts], bool(a1))
print(max(ts), min(ts), sorted(ts))
print(timedelta(days=1, seconds=1).total_seconds(), timedelta(microseconds=-1).total_seconds(),
      timedelta(days=106751).total_seconds(), timedelta(seconds=1e-6).total_seconds())


# Methods, closures and module-level values.
class Timer:
    def __init__(self, limit: timedelta) -> None:
        self.limit = limit
        self.spent = timedelta()

    def add(self, seconds: float) -> bool:
        self.spent += timedelta(seconds=seconds)
        return self.spent > self.limit


def scaler(factor: float) -> Callable[[timedelta], timedelta]:
    return lambda td: td * factor


tm = Timer(timedelta(minutes=1))
print([tm.add(s) for s in [10.5, 20.25, 29.25, 0.000001]], tm.spent)
half = scaler(0.5)
print(half(timedelta(hours=1)), half(timedelta(microseconds=3)), half(timedelta(microseconds=-3)))
none_td: timedelta | None = None
if len(ts) > 99:
    none_td = timedelta(1)
show("td == None", lambda: str(t1 == none_td) + " " + str(t1 != none_td))
show("td < None", lambda: str(t1 < none_td))
show("td + None", lambda: str(t1 + none_td))
show("td // float", lambda: str(t1 // 2.5))
