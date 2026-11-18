"""Each kind of memory access that Pystachy's compiler emits without its runtime check.

tools/check_lean_access.py proves each one safe with Lean: a list item read within the list's
length, and a dict entry reused while it is still live.
"""

from typing import Iterator

TABLE: dict[str, int] = {"a": 1, "b": 2}


class Cache:
    def __init__(self) -> None:
        self.hits = 0
        self.table: dict[str, int] = {"x": 10}

    def lookup(self, key: str) -> int:
        # dictfuse: the second read of self.table reuses the entry the test found; the
        # write to another field of the class between them changes no dict
        if key in self.table:
            self.hits += 1
            return self.table[key]
        return -1


def item(xs: list[int], i: int) -> int:
    # listfast: an unsigned test of the index against the length just read
    return xs[i]


def last(xs: list[int]) -> int:
    # listfast of a negative literal: the inline read's test never passes
    return xs[-1]


def pair(xs: list[int]) -> int:
    # unpacking: the runtime checks the length is 2 before reading items 0 and 1
    a, b = xs
    return a + b


def ends(xs: list[int]) -> int:
    # starred unpacking: items 0 and len - 1 after the check that the length is at least 2
    a, *middle, c = xs
    return a + c + len(middle)


def tail3(xs: list[int]) -> int:
    # starred unpacking's last items: len - 3, then + 1 and + 2, none past the length
    a, *middle, c, d, e = xs
    return a + c + d + e + len(middle)


class Registry:
    names: dict[str, int] = {"r": 7}


def class_lookup(key: str) -> int:
    # dictfuse of a class variable, which machine loads read, reloaded where nothing writes it
    if key in Registry.names:
        Registry.names[key] += 1
    return Registry.names.get(key, 0)


def total(xs: list[int]) -> int:
    # listget: a sequence loop reads each item behind its test of the current length
    t = 0
    for x in xs:
        t += x
    return t


def odd_lengths(xs: list[str]) -> int:
    # listget: a range loop reads behind a length read once, before the loop, in a function
    # that writes no list
    t = 0
    for i in range(1, len(xs), 2):
        t += len(xs[i])
    return t


def ranked(xs: list[str]) -> list[str]:
    # a key function's loop over a copy reads the copy's length from its header
    return sorted(xs, key=len)


def counted(d: dict[str, int], key: str) -> int:
    # dictfuse: the lookup's entry, read and then written back
    if key in d:
        d[key] = d[key] + 1
        return d[key]
    return 0


def global_lookup(key: str) -> int:
    # dictfuse of a module global, reloaded where nothing writes globals
    if key in TABLE:
        return TABLE[key]
    return 0


def every_other(xs: list[str]) -> Iterator[str]:
    # a generator's caller runs at each yield and may shorten xs: listget leaves this range
    # loop's reads checked
    for i in range(0, len(xs), 2):
        yield xs[i]


def smoothed(a: list[float], b: list[float]) -> None:
    # listguard: a copy of the loop reads a[i - 1], a[i] and a[i + 1] and assigns b[i] unchecked,
    # where tests before it find len(a) - 1 and len(b) at least the loop's stop
    for i in range(1, len(a) - 1):
        b[i] = (a[i - 1] + a[i] + a[i + 1]) / 3.0


def pairs(xs: list[int]) -> int:
    # listguard with a constant stop: xs[i] and xs[i + 1] for i < 4, where len(xs) - 1 >= 4
    s = 0
    for i in range(4):
        s += xs[i] * xs[i + 1]
    return s


def shifted(xs: list[int]) -> int:
    # listguard with a negative offset, a 1-based loop: xs[i - 1] for 1 <= i < len(xs) + 1, where
    # the test before it finds the stop at most len(xs) + 1 (a length plus one never wraps)
    s = 0
    for i in range(1, len(xs) + 1):
        s += xs[i - 1]
    return s


def rows(data: list[float], i: int, j: int, dim: int) -> float:
    # listguard with a base: data[bi + d] and data[bj + d] for d < dim, where tests before the loop
    # find bi and bj at least 0 and dim plus each at most len(data); the copy adds each base to d
    # without an overflow check
    bi = i * dim
    bj = j * dim
    s = 0.0
    for d in range(dim):
        diff = data[bi + d] - data[bj + d]
        s += diff * diff
    return s


def main() -> None:
    cache = Cache()
    print(item([1, 2, 3], 1), last([4, 5]), pair([4, 5]), ends([1, 2, 3, 4]), total([1, 2, 3]))
    print(tail3([1, 2, 3, 4, 5]), class_lookup("r"), class_lookup("q"))
    print(odd_lengths(["a", "bb", "c", "ddd"]), ranked(["ccc", "a", "bb"]))
    print(counted({"k": 1}, "k"), global_lookup("b"), cache.lookup("x"), cache.lookup("y"), cache.hits)
    print(list(every_other(["a", "b", "c"])))
    smooth = [0.0] * 5
    smoothed([1.0, 2.0, 3.0, 4.0, 5.0], smooth)
    print(smooth, pairs([1, 2, 3, 4, 5]), shifted([1, 2, 3]), rows([1.0, 2.0, 3.0, 5.0], 0, 1, 2))


main()
