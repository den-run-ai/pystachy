"""repr(), == and ordering by a type descriptor, whose walks moved to runtime.py. Inputs are built before timing."""
import sys
from time import perf_counter


def repr_ints(n: int, xs: list[int]) -> int:
    # repr of a list of ints: the walk writes each int's digits into its text
    total = 0
    for i in range(n):
        total += len(repr(xs))
    return total


def repr_strs(n: int, ws: list[str]) -> int:
    # of strs: quotes and escapes, a run of printable bytes at a time
    total = 0
    for i in range(n):
        total += len(repr(ws))
    return total


def repr_floats(n: int, fs: list[float]) -> int:
    total = 0
    for i in range(n):
        total += len(repr(fs))
    return total


def repr_nested(n: int, d: dict[str, list[tuple[int, str]]]) -> int:
    # a dict of lists of tuples: the walk's dispatch on each part
    total = 0
    for i in range(n):
        total += len(repr(d))
    return total


def eq_tuples(n: int, a: list[tuple[int, str]], b: list[tuple[int, str]]) -> int:
    # == of lists of tuples, equal but for the last item at times
    total = 0
    for i in range(n):
        if a == b:
            total += 1
        b[63] = (63 if i & 1 else 62, "w63")
    return total


def eq_dicts(n: int, a: dict[str, list[int]], b: dict[str, list[int]]) -> int:
    # == of dicts of lists: a lookup of each key, then the lists' items
    total = 0
    for i in range(n):
        if a == b:
            total += 1
    return total


def sort_tuples(n: int, ts: list[tuple[int, str]]) -> int:
    # sorted() of tuples: each comparison is the ordering's walk
    total = 0
    for i in range(n):
        s = sorted(ts)
        total += s[i & 255][0]
    return total


def in_tuples(n: int, ts: list[tuple[int, int]]) -> int:
    # x in a list of tuples: each item's == by its descriptor
    total = 0
    for i in range(n):
        if (i & 127, (i >> 7) & 3) in ts:
            total += 1
    return total


def order_lists(n: int, xs: list[list[int]]) -> int:
    # < of lists of ints, which differ late
    total = 0
    for i in range(n):
        if xs[i & 15] < xs[(i * 7) & 15]:
            total += 1
    return total


kind = sys.argv[1]
n = int(sys.argv[2])
ints = [i * 7919 - 100000 for i in range(64)]
strs = ["w" + str(i) + ("'" if i % 5 == 0 else "") for i in range(64)]
floats = [i / 7 for i in range(64)]
nested = {"k" + str(i): [(j, "v" + str(j)) for j in range(4)] for i in range(16)}
pairs = [(i, "w" + str(i)) for i in range(64)]
pairs2 = [(i, "w" + str(i)) for i in range(64)]
lists_a = {"k" + str(i): [j for j in range(16)] for i in range(16)}
lists_b = {"k" + str(i): [j for j in range(16)] for i in range(16)}
unsorted = [((i * 37) & 255, "s" + str(i & 7)) for i in range(256)]
haystack = [(i & 127, (i >> 3) & 3) for i in range(128)]
rows = [[j for j in range(31)] + [i] for i in range(16)]
start = perf_counter()
if kind == "walk-repr-ints":
    result = repr_ints(n, ints)
elif kind == "walk-repr-strs":
    result = repr_strs(n, strs)
elif kind == "walk-repr-floats":
    result = repr_floats(n, floats)
elif kind == "walk-repr-nested":
    result = repr_nested(n, nested)
elif kind == "walk-eq-tuples":
    result = eq_tuples(n, pairs, pairs2)
elif kind == "walk-eq-dicts":
    result = eq_dicts(n, lists_a, lists_b)
elif kind == "walk-sort-tuples":
    result = sort_tuples(n, unsorted)
elif kind == "walk-in-tuples":
    result = in_tuples(n, haystack)
elif kind == "walk-order-lists":
    result = order_lists(n, rows)
else:
    raise ValueError("unknown workload")
elapsed = perf_counter() - start
print(result, elapsed)
