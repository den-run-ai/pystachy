# pystachy: python-int
# The separator group size accepts promoting ints, retaining C-int range checks.
def grouped(n: int) -> str:
    return b"\x01\x02\x03\x04".hex(":", n)


def optional_grouped(n: int | None) -> str:
    return b"\x01\x02\x03\x04".hex("-", n)


for n in [1, 2, -2, 0, 2 ** 31, -2 ** 31 - 1, 2 ** 70, -(2 ** 70)]:
    try:
        print(grouped(n))
    except OverflowError as e:
        print(type(e).__name__, str(e))
print(optional_grouped(2))
try:
    print(optional_grouped(None))
except TypeError as e:
    print(type(e).__name__, str(e))
