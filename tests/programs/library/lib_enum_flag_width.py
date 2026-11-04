from enum import Flag, IntFlag


class Dense(IntFlag):
    A = 1
    HIGH = 1 << 62


class Sparse(IntFlag):
    A = 1
    PAIR = (1 << 62) | A


class Small(IntFlag):
    A = 1


class Strict(Flag):
    A = 1
    PAIR = (1 << 62) | A


for n in [-1, -2, -(1 << 62), -(1 << 62) - 1, -9223372036854775807, -9223372036854775807 - 1]:
    dense = Dense(n)
    sparse = Sparse(n)
    print(n, dense.value, dense.name, sparse.value, sparse.name)
print((~Dense.A).value, (~Sparse.A).value)
print(Small(-9223372036854775807).value)

# With the smaller class's mask the minimum negative input converts to 2**63.
# CPython's result is out of range; Pystachy must not wrap it into a signed int.
try:
    n = Small(-9223372036854775807 - 1).value
    print("out of range" if n > 9223372036854775807 else str(n))
except OverflowError:
    print("out of range")


# An invalid negative strict flag value should retain CPython's error and bit
# diagram, even when formatting the given value uses 63 binary digits.
try:
    Strict(-(1 << 62) - 1)
except ValueError as exc:
    print(str(exc))
