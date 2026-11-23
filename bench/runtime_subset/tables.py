"""Set operations whose table code moved to runtime.py. A case that only reads its inputs builds them before timing."""
import sys
from time import perf_counter


def add_ints(n: int) -> int:
    # adds to one set that is cleared every 4,096 elements: growth from the least table
    total = 0
    s: set[int] = set()
    for i in range(n):
        s.add(i * 7)
        if len(s) == 4096:
            total += 1
            s.clear()
    return total + len(s)


def has_ints(n: int, s: set[int]) -> int:
    # lookups in a table that fits in the cache, half of them misses
    total = 0
    for i in range(n):
        if (i & 2047) in s:
            total += 1
    return total


def has_ints_large(n: int, s: set[int]) -> int:
    # and in one that does not: each probe is a cache miss
    total = 0
    k = 12345
    for i in range(n):
        k = (k * 1103515245 + 12345) & 2097151
        if k in s:
            total += 1
    return total


def churn_ints(n: int) -> int:
    # adds and discards, whose dummies make the table rebuild
    total = 0
    s: set[int] = set()
    for i in range(n):
        s.add(i & 1023)
        s.discard((i * 5 + 3) & 1023)
        total += len(s) & 1
    return total + len(s)


def add_has_strs(n: int, words: list[str]) -> int:
    total = 0
    s: set[str] = set()
    for i in range(n):
        s.add(words[i & 255])
        if words[(i * 7) & 255] in s:
            total += 1
        if (i & 1023) == 1023:
            s.clear()
    return total + len(s)


def add_has_tuples(n: int) -> int:
    # elements that a type descriptor describes: compared in runtime.c
    total = 0
    s: set[tuple[int, int]] = set()
    for i in range(n):
        t = (i & 127, i & 3)
        if t in s:
            total += 1
        else:
            s.add(t)
        if len(s) == 300:
            s.clear()
    return total + len(s)


def set_algebra(n: int, a: set[int], b: set[int]) -> int:
    total = 0
    for i in range(n):
        total += len(a | b) + len(a & b) + len(a - b) + len(a ^ b)
    return total


def iterate(n: int, s: set[int]) -> int:
    total = 0
    for i in range(n):
        for x in s:
            total += x
    return total


def update_lists(n: int, xs: list[int]) -> int:
    total = 0
    for i in range(n):
        s: set[int] = set()
        s.update(xs)
        s.difference_update(xs[:40])
        total += len(s)
    return total


def pop_all(n: int, xs: list[int]) -> int:
    total = 0
    for i in range(n):
        s = set(xs)
        while s:
            total += s.pop() & 1
    return total


def compare_sets(n: int, a: set[int], b: set[int]) -> int:
    total = 0
    c = set(a)
    for i in range(n):
        if a == c:
            total += 1
        if b <= a:
            total += 1
        if a.isdisjoint(b):
            total += 1
    return total


kind = sys.argv[1]
n = int(sys.argv[2])
words = ["w" + str(i) for i in range(256)]
nums = [(i * 16411) % 65537 for i in range(128)]
small = set(range(0, 2048, 2))
left = set(range(0, 192))
right = set(range(96, 288))
large: set[int] = set()
if kind == "set-has-large":
    large = set(range(0, 2097152, 2))
start = perf_counter()
if kind == "set-add":
    result = add_ints(n)
elif kind == "set-has":
    result = has_ints(n, small)
elif kind == "set-has-large":
    result = has_ints_large(n, large)
elif kind == "set-churn":
    result = churn_ints(n)
elif kind == "set-str":
    result = add_has_strs(n, words)
elif kind == "set-tuple":
    result = add_has_tuples(n)
elif kind == "set-algebra":
    result = set_algebra(n, left, right)
elif kind == "set-iterate":
    result = iterate(n, small)
elif kind == "set-update-list":
    result = update_lists(n, nums)
elif kind == "set-pop":
    result = pop_all(n, nums)
elif kind == "set-compare":
    result = compare_sets(n, left, right)
else:
    raise ValueError("unknown workload")
elapsed = perf_counter() - start
print(result, elapsed)
