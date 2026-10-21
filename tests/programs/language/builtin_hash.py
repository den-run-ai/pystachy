# hash(): CPython's values where its own do not change from run to run (an int's, a bool's, a
# float's, None's, a tuple's of such items, what a __hash__ returns); a str's and an object's
# identity hash only equal for equal strs and for the same object. Unhashable types raise TypeError


class Ident:
    pass


class Pt:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Pt) and self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))


class EqOnly:
    def __eq__(self, other: object) -> bool:
        return True


class HashAgain(EqOnly):
    def __hash__(self) -> int:
        return 42


print(hash(0), hash(1), hash(-1), hash(-2), hash(True), hash(False), hash(10**18))
print(hash(2**61 - 2), hash(2**61 - 1), hash(2**61), hash(-(2**61)), hash(9223372036854775807), hash(-9223372036854775807 - 1))
print(hash(0.0), hash(-0.0), hash(1.0), hash(-1.0), hash(0.5), hash(-2.5), hash(1e300), hash(1e-300), hash(5e-324))
print(hash(float("inf")), hash(float("-inf")), hash(3.0) == hash(3), hash(2.0**70) == 2**9)  # (2**61 is 1 modulo 2**61 - 1)
print(hash(1.1), hash(-123.456), hash(2.0**-1074), hash(1.7976931348623157e308))
print(hash(()), hash((1,)), hash((1, 2)), hash((1, (2, 3), True)), hash((-1, -2)), hash((0.5, None)))
print(hash(None), hash((None,)), hash(((), ((),))))
x: int | None = None
f: float | None = 2.5


def get(s: str) -> str | None:
    return None if s == "" else s


print(hash(x) == hash(None), hash(f) == hash(2.5), hash(get("")) == hash(None), hash(get("é")) == hash("é"))
x = 7
print(hash(x))
t = tuple([1, 2, 3])
print(hash(t) == hash((1, 2, 3)), hash(tuple(["a"])) == hash(("a",)))
print(hash("abc") == hash("ab" + "c"), hash("") == hash(""), hash("ü€") == hash("ü" + "€"), hash(("a", 1)) == hash(("a", 1)))
a = Ident()
b = Ident()
print(hash(a) == hash(a), hash(a) == hash(b), hash((a, 1)) == hash((a, 1)))
print(hash(Pt(1, 2)) == hash((1, 2)), hash(Pt(1, 2)), hash(HashAgain()))
for v in [EqOnly()]:
    try:
        print(hash(v))
    except TypeError as e:
        print("TypeError:", e)
try:
    print(hash((1, EqOnly())))
except TypeError as e:
    print("TypeError:", e)
try:
    print(hash([1, 2]))
except TypeError as e:
    print("TypeError:", e)
try:
    print(hash({"k": 1}))
except TypeError as e:
    print("TypeError:", e)
try:
    print(hash({1}))
except TypeError as e:
    print("TypeError:", e)


def h(v) -> int:  # (a template: each call's type)
    return hash(v)


print(h(3), h(3.0), h((3,)), h(Pt(0, 0)) == hash((0, 0)))
