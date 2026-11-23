"""Dict operations whose table code moved to runtime.py. A case that only reads its inputs builds them before timing."""
import sys
from time import perf_counter


def set_ints(n: int) -> int:
    # stores into one dict that is cleared every 4,096 keys: growth from no table
    total = 0
    d: dict[int, int] = {}
    for i in range(n):
        d[i * 7] = i
        if len(d) == 4096:
            total += d[(i - 5) * 7]
            d.clear()
    return total + len(d)


def get_ints(n: int, d: dict[int, int]) -> int:
    # lookups in a table that fits in the cache, half of them misses
    total = 0
    for i in range(n):
        total += d.get(i & 2047, 1)
    return total


def get_ints_large(n: int, d: dict[int, int]) -> int:
    # and in one that does not
    total = 0
    k = 12345
    for i in range(n):
        k = (k * 1103515245 + 12345) & 2097151
        if k in d:
            total += d[k]
    return total


def count_words(n: int, words: list[str]) -> int:
    # the counting loop: a lookup and a store per word
    total = 0
    d: dict[str, int] = {}
    for i in range(n):
        w = words[(i * 7) & 255]
        d[w] = d.get(w, 0) + 1
        if (i & 4095) == 4095:
            total += d[w]
            d.clear()
    return total + len(d)


def tuple_keys(n: int) -> int:
    # keys that a type descriptor describes: hashed and compared in runtime.c
    total = 0
    d: dict[tuple[int, int], int] = {}
    for i in range(n):
        t = (i & 127, i & 3)
        if t in d:
            total += d[t]
        else:
            d[t] = i & 15
    return total + len(d)


def churn_dict(n: int) -> int:
    # stores and deletions, whose holes make the table rebuild
    total = 0
    d: dict[int, int] = {}
    for i in range(n):
        d[i & 1023] = i
        k = (i * 5 + 3) & 1023
        if k in d:
            del d[k]
        total += len(d) & 1
    return total + len(d)


def iterate_dict(n: int, d: dict[int, int]) -> int:
    total = 0
    for i in range(n):
        for k, v in d.items():
            total += k + v
    return total


def copy_update(n: int, a: dict[int, int], b: dict[int, int]) -> int:
    total = 0
    for i in range(n):
        c = a.copy()
        c.update(b)
        e = dict(c)
        total += len(e)
    return total


def pop_items(n: int, a: dict[int, int]) -> int:
    total = 0
    for i in range(n):
        c = dict(a)
        for k in range(0, 64, 2):
            total += c.pop(k, 0)
        while c:
            kv = c.popitem()
            total += kv[1] & 1
    return total


def columns(n: int, d: dict[int, int]) -> int:
    total = 0
    for i in range(n):
        total += len(list(d.keys())) + len(list(d.values()))
    return total


def defaults(n: int, words: list[str]) -> int:
    total = 0
    d: dict[str, int] = {}
    for i in range(n):
        total += d.setdefault(words[i & 255], i & 7)
        if (i & 2047) == 2047:
            d.clear()
    return total + len(d)


kind = sys.argv[1]
n = int(sys.argv[2])
words = ["w" + str(i) for i in range(256)]
table = {k: k & 15 for k in range(0, 2048, 2)}
low = {k: k for k in range(0, 192)}
high = {k: -k for k in range(96, 288)}
wide: dict[int, int] = {}
if kind == "dict-get-large":
    wide = {k: k & 7 for k in range(0, 2097152, 2)}
start = perf_counter()
if kind == "dict-set":
    result = set_ints(n)
elif kind == "dict-get":
    result = get_ints(n, table)
elif kind == "dict-get-large":
    result = get_ints_large(n, wide)
elif kind == "dict-str":
    result = count_words(n, words)
elif kind == "dict-tuple":
    result = tuple_keys(n)
elif kind == "dict-churn":
    result = churn_dict(n)
elif kind == "dict-iterate":
    result = iterate_dict(n, table)
elif kind == "dict-copy":
    result = copy_update(n, low, high)
elif kind == "dict-pop":
    result = pop_items(n, low)
elif kind == "dict-columns":
    result = columns(n, table)
elif kind == "dict-setdefault":
    result = defaults(n, words)
else:
    raise ValueError("unknown workload")
elapsed = perf_counter() - start
print(result, elapsed)
