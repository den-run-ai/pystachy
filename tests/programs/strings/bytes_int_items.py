# A bytes object is a sequence of ints wherever its items are taken: tuple(), starred items,
# set methods' iterables, dict.fromkeys(), slice assignment and starred targets.
data = b"Pys"
print(tuple(data), tuple(b""), [*data], (*data, 0), [0, *b"\x01\x02", 3])
s = {1}
s.update(b"\x01\x02")
print(sorted(s), s.issubset(b"\x00\x01\x02"), s.isdisjoint(b"\x07"), sorted(s.union(b"\x09")))
nones: dict[int, int | None] = dict.fromkeys(b"ab")
print(nones, dict.fromkeys(data, 0), dict.fromkeys(b"", 1))
xs = [1, 2, 3]
xs[1:2] = b"AB"
print(xs)
xs[::2] = b"xy"
print(xs)
try:
    xs[::2] = b"q"
except ValueError as e:
    print("ValueError:", e)
first, *rest = data
print(first, rest)
*init, last = b"\x00\xff"
print(init, last)
a, *mid, z = b"az"
print(a, mid, z)
try:
    p, q, *r = b"p"
except ValueError as e:
    print("ValueError:", e)


def items(x: bytes) -> list[int]:
    return [*x, len(x)]


print(items(b""), items(b"z"))
