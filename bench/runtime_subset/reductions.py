"""List reductions, joins and path joins moved to runtime.py; the timed region excludes inputs."""
import os
import sys
from time import perf_counter


def any_all(n: int, zeros: list[int], ones: list[int]) -> float:
    # a full scan each: the only nonzero item of zeros is its last, and ones has no zero
    total = 0
    for i in range(n):
        zeros[i % 64] = 0
        total += int(any(zeros)) + int(all(ones)) + i % 3
    return float(total)


def any_all_short(n: int, lists: list[list[int]]) -> float:
    total = 0
    for i in range(n):
        xs = lists[i % len(lists)]
        total += int(any(xs)) + 2 * int(all(xs))
    return float(total)


def sum_ints(n: int, xs: list[int]) -> float:
    total = 0.0
    for i in range(n):
        total += sum(xs, float(i % 7))
    return total


def join(n: int, sep: str, words: list[str]) -> float:
    total = 0
    for i in range(n):
        words[i % 16] = "ab" if i % 2 == 0 else "c"
        text = sep.join(words)
        total += len(text) + ord(text[i % len(text)])
    return float(total)


def join_slice(n: int, sep: str, words: list[str]) -> float:
    total = 0
    for i in range(n):
        lo = i % 5
        text = sep.join(words[lo:-1])
        total += len(text) + ord(text[i % len(text)])
    return float(total)


def path_join(n: int, heads: list[str], tails: list[str]) -> float:
    total = 0
    for i in range(n):
        path = os.path.join(heads[i % len(heads)], tails[i % len(tails)])
        total += len(path) + (ord(path[len(path) - 1]) if len(path) > 0 else 0)
    return float(total)


kind = sys.argv[1]
n = int(sys.argv[2])
zeros = [0] * 4095 + [1]
ones = [1] * 4096
shorts = [[0, 0, 0, 1], [1, 2, 3, 4, 5, 6], [0], [7], [0, 0, 0, 0, 0, 0, 0, 0], [1, 1, 0], [], [2, 0]]
ints = [(i * 2654435761) % 1000003 - 500000 for i in range(4096)]
words = ["w" + str(i % 97) for i in range(256)]
chars = [chr(97 + i % 26) for i in range(1024)]
heads = ["", "/", "usr", "usr/", "/var/lib/pystachy", "a/b/c/", "é", "relative/path/of/some/length"]
tails = ["file.txt", "/abs", "", "x", "nested/name.py", "€", "lib"]

begin = perf_counter()
value = 0.0
if kind == "ints-any-all":
    value = any_all(n, zeros, ones)
elif kind == "ints-any-all-short":
    value = any_all_short(n, shorts)
elif kind == "ints-sum-float":
    value = sum_ints(n, ints)
elif kind == "join":
    value = join(n, ", ", words)
elif kind == "join-bytes":
    value = join(n, "", chars)
elif kind == "join-slice":
    value = join_slice(n, "-", words)
elif kind == "path-join":
    value = path_join(n, heads, tails)
else:
    raise ValueError("unknown workload")
elapsed = perf_counter() - begin
print(value.hex(), elapsed)
