# list.insert() and list.index() with bounds beyond the list, decided at run time: insert() below
# -len(xs) puts the item first, index()'s start below -len(xs) searches from the first item, a
# negative stop counts from the end, and a stop before the item's place raises ValueError, as
# CPython's list_insert and list_index clamp them; also with the 64-bit extremes.
import sys

n = len(sys.argv)            # 3 (tests/run.sh passes a1 a2)
xs = [10, 20, 30, 20]
for i in [-100 * n, -len(xs) - 1, -len(xs), -1, 0, len(xs), 100 * n, -9223372036854775807 - 1, 9223372036854775807]:
    ys = xs.copy()
    ys.insert(i, 99)
    print(i, ys)
for start, stop in [(-100, 4), (-5, -1), (0, -1), (-4, -2), (1, 3), (2, 100), (-9223372036854775807 - 1, 9223372036854775807)]:
    try:
        print(start, stop, xs.index(20, start, stop))
    except ValueError as e:
        print(start, stop, "ValueError:", e)
for start, stop in [(0, 1), (2, 3), (0, -3), (-1, -1), (3, -100)]:
    try:
        print(start, stop, xs.index(20, start, stop))
    except ValueError as e:
        print(start, stop, "ValueError:", e)
strs = ["a", "b", "a"]
print(strs.index("a", -10), strs.index("a", 1), strs.index("a", -2, n))
try:
    strs.index("b", 0, -2)
except ValueError as e:
    print("ValueError:", e)
