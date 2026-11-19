# bytearray(): each form of its arguments, what the builtins make of one, and its errors


class Holder:
    def __init__(self, data: bytearray) -> None:
        self.data = data


def describe(b: bytearray) -> str:
    return f"{b!r} len={len(b)} bool={bool(b)} bytes={bytes(b)!r} list={list(b)}"


def grow(b: bytearray, n: int) -> int:
    for i in range(n):
        b.append(i % 251)
    return len(b)


empty = bytearray()
zeros = bytearray(5)
copied = bytearray(b"abc\x00\xff'\"")
again = bytearray(copied)
ints = bytearray([104, 105, 0, 255])
ranged = bytearray(range(65, 70))
gen = bytearray(x * 2 for x in [1, 2, 3])
tup = bytearray((1, 2, 3))
text = bytearray("héllo", "utf-8")
latin = bytearray("héllo", "latin-1")
replaced = bytearray("héllo", "ascii", "replace")
kw = bytearray("abc", encoding="ascii")
for b in [empty, zeros, copied, again, ints, ranged, gen, tup, text, latin, replaced, kw]:
    print(describe(b))
print(again == copied, again is copied, bytearray(0) == empty, bytearray(b"") == b"")

for n in [-1]:
    try:
        bytearray(n)
    except ValueError as e:
        print("ValueError:", e)
for xs in [[1, 256], [-1], [0, 1, 2, 300, 4]]:
    try:
        bytearray(xs)
    except ValueError as e:
        print("ValueError:", e)
try:
    bytearray("abc")
except TypeError as e:
    print("TypeError:", e)
try:
    bytearray(b"abc", "ascii")
except TypeError as e:
    print("TypeError:", e)
try:
    bytearray("abc", "no-such-codec")
except LookupError as e:
    print("LookupError:", e)
try:
    bytearray("hé", "ascii")
except UnicodeEncodeError as e:
    print("UnicodeEncodeError:", e)

b = bytearray(b"cab")
print(sorted(b), max(b), min(b), sum(b), list(enumerate(b)), list(reversed(b)), [x for x in b if x > 97])
x, y, z = b
print(x, y, z, 97 in b, 100 in b, b"ab" in b, b"ba" in b, bytearray(b"a") in b, b"" in b)
print(isinstance(b, bytearray), isinstance(b"cab", bytearray), isinstance(b, bytes), type(b).__name__, type(b) is bytearray)
print(b == b"cab", b != b"cab", b == bytearray(b"cab"), b == "cab", b == 3, b != None, b < b"cb", b <= bytearray(b"cab"), b > b"c", b >= b"cab\x00")
try:
    print(256 in b)
except ValueError as e:
    print("ValueError:", e)
try:
    print(hash(b))
except TypeError as e:
    print("TypeError:", e)
try:
    print(b < 3)
except TypeError as e:
    print("TypeError:", e)

h = Holder(b)
alias = h.data
alias.append(33)
many = [b, bytearray(b"x")]
many[0].append(63)
table = {"k": b}
table["k"].extend(b"..")
print(b, h.data, alias is b, many, table, grow(b, 1000), len(b), b[-1], b[500], bytes(b[:8]))
print(str(b[:3]), repr(b[:3]), f"{b[:3]}", "%s %r" % (b[:3], b[:3]), [b[:2]], (b[:1],))
c = b.copy()
c.clear()
print(len(c), c, len(b), bool(c), not c)
it = iter(bytearray(b"xyz"))
print(next(it), next(it), next(it), next(it, -1))
live = bytearray(b"ab")
seen = []
for v in live:
    seen.append(v)
    if len(live) < 5:
        live.append(v + 2)
print(seen, live)
