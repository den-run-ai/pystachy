# pystachy: python-int
# Documented deviation (docs/python-int.md#64-bit-boundaries): a promoting int is two words in
# variables, arguments, returns, fields, globals, closures, tuples, int | None, lists of ints and of
# tuples of ints, the keys and values of dicts of ints, sets of ints and generators, but 64-bit
# storage and the builtins that take an int keep 64-bit ints for now (#907). A value past 64 bits
# stored in an int | None in a list, a tuple's int | None item, the union of a bool and an int (a
# result that is either) or sent to a generator, given to range(), added by sum() among floats, in a
# NamedTuple that may be None (a parameter) hashed as the tuple of its fields, a list's tuple that
# set() takes, or whose tuple dict() takes as a value, or a list's item (a tuple's too), a dict's
# key, a set's element or a generator's value that tuple() or a module that does not opt in (heapq,
# the iterator of iter()) reads, raises OverflowError, where CPython goes on with the bigger int.
# A tuple of 64-bit ints one of whose items is -2**63 becomes a new tuple where a tuple of promoting
# ints is expected, as in a list of tuples of ints.
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
pairs = [(big, 1)]
try:
    print(set(pairs))
except OverflowError as e:
    print("set() of a list of tuples:", e)
try:
    print(dict([(1, (big, 1))]))
except OverflowError as e:
    print("dict() of pairs of tuples:", e)
try:
    print(heapq.heappop(pairs))
except OverflowError as e:
    print("tuple in a list in heapq:", e)
keyed = {big: "k"}
try:
    print(next(iter(keyed)))
except OverflowError as e:
    print("iter() of a dict:", e)
try:
    print(next(iter({big})))
except OverflowError as e:
    print("iter() of a set:", e)
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
for p in enumerate([5], -2 ** 63):
    q: tuple[int, int] = p
    print("tuple identity:", q == p, q is p)
keys = {p: 1}
print("tuple identity in a list of keys:", list(keys)[0] == p, list(keys)[0] is p)
print("tuple identity in a dict's items:", list(keys.items())[0][0] is p, list({1: p}.items())[0][1] is p)
xs.append(big - 2 ** 63 - 1)
print(xs, (big - 1) in xs, big in xs, [x * big for x in [0]], 2 ** 62 / 2, hex(big - 2 ** 63 - 1), (2 ** 63 - 1).bit_length())
