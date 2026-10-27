# pystachy: python-int
# Documented deviation (docs/python-int.md#64-bit-boundaries): a promoting int is two words in
# variables, arguments, returns, fields, globals, closures, tuples, int | None, lists of ints, the
# values of dicts of ints, sets of ints and generators, but 64-bit storage and the builtins that take
# an int keep 64-bit ints for now (#907). A value past 64 bits stored as a dict's key, in a tuple or
# an int | None in a list, a tuple's int | None item, the union of a bool and an int (a result that
# is either) or sent to a generator, given to range(), added by sum() among floats, in a NamedTuple
# that may be None (a parameter) hashed as the tuple of its fields, a dict's value that items() or
# popitem() puts in a tuple, or a list's item, a set's element or a generator's value that tuple()
# or a module that does not opt in (heapq, the iterator of iter()) reads, raises OverflowError,
# where CPython goes on with the bigger int; so does pop() of a bool key, which reads a dict's
# values as 64-bit ints.
# A tuple of 64-bit ints one of whose items is -2**63 becomes a new tuple where a tuple of promoting
# ints is expected.
import heapq
from typing import Generator, NamedTuple


def gen(n: int):
    yield n


def echo() -> Generator[int, int | None, None]:
    got = yield 0
    yield got if got is not None else -1


def flag_or(c: bool, n: int):
    if c:
        return c
    return n


class Ratio(NamedTuple):
    num: int
    den: int


def ratio_hash(r: Ratio) -> int:
    return hash(r)


big = 2 ** 64
xs = [1, 2]
ys = [big, 1]
try:
    print(tuple(ys))
except OverflowError as e:
    print("tuple of a list:", e)
try:
    heapq.heappush(ys, 0)
except OverflowError as e:
    print("heapq:", e, ys)
try:
    pairs = [(big, 1)]
    print(pairs)
except OverflowError as e:
    print("tuple in a list:", e)
try:
    print({big: "k"})
except OverflowError as e:
    print("dict key:", e)
try:
    print(next(iter({big})))
except OverflowError as e:
    print("iter() of a set:", e)
vals = {"k": big}
try:
    print(list(vals.items()))
except OverflowError as e:
    print("items():", e)
try:
    print(vals.popitem())
except OverflowError as e:
    print("popitem():", e, vals)
try:
    flagged = {1: 2, 2: big}
    print(flagged.pop(True))
except OverflowError as e:
    print("pop() of a bool key:", e, flagged)
maybe: int | None = big
try:
    print([maybe])
except OverflowError as e:
    print("int | None in a list:", e)
try:
    print((maybe, 1))
except OverflowError as e:
    print("int | None in a tuple:", e)
try:
    print(heapq.nlargest(1, gen(big)))
except OverflowError as e:
    print("generator in heapq:", e)
try:
    g = echo()
    next(g)
    print(g.send(big))
except OverflowError as e:
    print("send:", e)
try:
    print(flag_or(True, 1), flag_or(False, big))
except OverflowError as e:
    print("bool join:", e)
try:
    print(range(big))
except OverflowError as e:
    print("range:", e)
try:
    mixed: list[int | float] = [2 ** 62, 2 ** 62, 0.5]
    print(sum(mixed))
except OverflowError as e:
    print("sum:", e)
try:
    print(big in [1.8446744073709552e19])
except OverflowError as e:
    print("in:", e)
try:
    print(ratio_hash(Ratio(3, 4)) == hash((3, 4)))
    print(ratio_hash(Ratio(big, 3)))
except OverflowError as e:
    print("NamedTuple:", e)
p = list(enumerate([5], -2 ** 63))[0]
q: tuple[int, int] = p
print("tuple identity:", q == p, q is p)
xs.append(big - 2 ** 63 - 1)
print(xs, (big - 1) in xs, big in xs, [x * big for x in [0]], 2 ** 62 / 2, hex(big - 2 ** 63 - 1), (2 ** 63 - 1).bit_length())
