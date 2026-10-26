# pystachy: python-int
# Documented deviation (docs/python-int.md#64-bit-boundaries): a promoting int is two words in
# variables, arguments, returns, fields, globals, closures, tuples and int | None, but 64-bit
# storage and the builtins that take an int keep 64-bit ints for now (#907). A value past 64 bits
# stored in a list, dict or set (also in a tuple or an int | None there), a tuple's int | None item
# or a generator's yield, given to range(), added by sum() among floats, or in a NamedTuple that may
# be None (a parameter) hashed as the tuple of its fields, raises OverflowError, where CPython goes
# on with the bigger int.
# A tuple of 64-bit ints one of whose items is -2**63 becomes a new tuple where a tuple of promoting
# ints is expected.
from typing import NamedTuple


def gen(n: int):
    yield n


class Ratio(NamedTuple):
    num: int
    den: int


def ratio_hash(r: Ratio) -> int:
    return hash(r)


big = 2 ** 64
xs = [1, 2]
try:
    xs.append(big)
except OverflowError as e:
    print("list:", e)
try:
    pairs = [(big, 1)]
    print(pairs)
except OverflowError as e:
    print("tuple in a list:", e)
try:
    d = {"k": big}
    print(d)
except OverflowError as e:
    print("dict:", e)
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
    for v in gen(big):
        print(v)
except OverflowError as e:
    print("yield:", e)
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
