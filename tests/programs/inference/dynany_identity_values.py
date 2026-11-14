# pystachy: dynamic-any
# Numbers that re's Pattern/Match and datetime's objects give back are new objects, as those
# of CPython's C modules (_sre, _datetime) are; module variables, named tuples and exceptions
# keep their objects (docs/dynamic-any.md#numeric-value-modules).
import datetime
import re
from typing import Any

p = re.compile("a")
s = "x" * 1000 + "a"
pos = 1000
m = p.search(s, pos)
assert m is not None
a: Any = m.end()
b: Any = m.end()
print("end is end", a is b, a == b)
c: Any = m.pos
d: Any = pos
print("pos is pos", c is d, c == d)
day = datetime.date(2024, 5, 6)
y1: Any = day.year
y2: Any = day.year
print("year is year", y1 is y2, y1 == y2)
td = datetime.timedelta(days=5000)
d1: Any = td.days
d2: Any = td.days
print("days is days", d1 is d2, d1 == d2)
top1: Any = datetime.MAXYEAR
top2: Any = datetime.MAXYEAR
print("MAXYEAR is MAXYEAR", top1 is top2)
cal = day.isocalendar()
w1: Any = cal.year
w2: Any = cal.year
print("isocalendar year is year", w1 is w2)
tt = day.timetuple()
t1: Any = tt.tm_year
t2: Any = tt.tm_year
print("timetuple year is year", t1 is t2)
try:
    re.compile("x" * 300 + "(")
except re.error as e:
    e1: Any = e.pos
    e2: Any = e.pos
    print("error pos is pos", e1 is e2, e.pos)
# Small ints are cached in both.
h1: Any = day.month
h2: Any = day.month
print("month is month", h1 is h2)
# An object of theirs as an Any value reads its fields' values.
boxed: Any = day
print("boxed year", boxed.year, boxed.year == 2024, boxed.year is boxed.year)
when: Any = datetime.datetime(2024, 5, 6, 7, 8, 9, tzinfo=datetime.timezone.utc)
print(when.hour, when.utcoffset(), when.isoformat())
print(m.span(), m.group(), td.total_seconds())
seen: list[Any] = [m.end(), m.end()]
print(seen[0] is seen[1], seen[0] in seen, len(set(seen)))
