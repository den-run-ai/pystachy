# pystachy: python-int
# Documented deviation (docs/python-int.md#64-bit-boundaries): a promoting int is two words in
# variables, arguments, returns, fields, globals and closures, but 64-bit storage and the builtins
# that take an int keep 64-bit ints for now (#907). A value past 64 bits stored in a list, dict,
# set, tuple, int | None (also x if c else None) or a generator's yield, given to range() or
# divmod(), or added by sum() among floats, raises OverflowError, where CPython goes on with the
# bigger int.


def gen(n: int):
    yield n


def square_or_none(n: int):
    return n * n if n > 0 else None


big = 2 ** 64
xs = [1, 2]
try:
    xs.append(big)
except OverflowError as e:
    print("list:", e)
try:
    pair = (big, 1)
    print(pair)
except OverflowError as e:
    print("tuple:", e)
try:
    d = {"k": big}
    print(d)
except OverflowError as e:
    print("dict:", e)
maybe: int | None = None
try:
    maybe = big
except OverflowError as e:
    print("optional:", e)
try:
    for v in gen(big):
        print(v)
except OverflowError as e:
    print("yield:", e)
try:
    print(square_or_none(big))
except OverflowError as e:
    print("join:", e)
try:
    print(range(big))
except OverflowError as e:
    print("range:", e)
try:
    print(divmod(big, 7))
except OverflowError as e:
    print("divmod:", e)
try:
    mixed: list[int | float] = [2 ** 62, 2 ** 62, 0.5]
    print(sum(mixed))
except OverflowError as e:
    print("sum:", e)
try:
    print(big in [1.8446744073709552e19])
except OverflowError as e:
    print("in:", e)
xs.append(big - 2 ** 63 - 1)
print(xs, (big - 1) in xs, big in xs, [x * big for x in [0]], 2 ** 62 / 2, hex(big - 2 ** 63 - 1), (2 ** 63 - 1).bit_length())
