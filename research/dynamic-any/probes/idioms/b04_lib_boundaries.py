# pystachy: dynamic-any
# Any values passed to library modules that do not opt in: heapq, bisect, textwrap, re, string
import bisect
import heapq
import re
import textwrap
from string import Template
from typing import Any

xs: list[Any] = [5, 1.5, 3, 2]
heapq.heapify(xs)
print([heapq.heappop(xs) for _ in range(4)])
ys: list[Any] = [1, 2.5, 4]
bisect.insort(ys, 3)
print(ys, bisect.bisect_left(ys, 2.5))
s: Any = "the quick brown fox jumps over the lazy dog"
print(textwrap.wrap(s, 12))
m = re.match(r"(\w+) (\w+)", s)
print(m.group(2) if m else None)
d: dict[str, Any] = {"who": "world", "n": 3}
print(Template("hello $who x$n").substitute(d))
