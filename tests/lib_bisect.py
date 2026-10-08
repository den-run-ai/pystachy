# CPython's own Lib/bisect.py (lib/bisect.py, unmodified): hi=None and key=None are
# parameters whose argument is None, so 'if hi is None:' and 'if key is None:' are decided
# when each call is compiled
import bisect
from bisect import bisect_left, bisect_right, insort, insort_left

a = [1, 2, 4, 4, 4, 8, 9]
for x in [0, 1, 4, 5, 9, 10]:
    print(x, bisect_left(a, x), bisect_right(a, x), bisect.bisect(a, x), bisect_left(a, x, 2), bisect_right(a, x, 1, 4), bisect_left(a, x, hi=3), bisect_right(a, x, lo=3, hi=6))
print(bisect_left(a, 4, key=None), bisect.bisect_right(a, 4, 0, None, key=None))
xs: list[int] = []
for v in [5, 1, 4, 1, 5, 9, 2, 6]:
    insort(xs, v)
    insort_left(xs, v * 10)
print(xs)
names = ["ann", "bob", "eve"]
bisect.insort_right(names, "dan")
bisect.insort(names, "amy", 1)
print(names, bisect.bisect(names, "carl"))
fs = [0.5, 1.5, 2.5]
bisect.insort(fs, 1.5)
print(fs, bisect.bisect_left(fs, 1.5), bisect.bisect_right(fs, 1.5))
grades = "FDCBA"
print([grades[bisect.bisect([60, 70, 80, 90], s)] for s in [33, 99, 77, 70, 89, 90, 100]])
print(bisect.bisect_left(a, 3, -1))
