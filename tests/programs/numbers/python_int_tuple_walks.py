# pystachy: python-int
# Tuples of promoting ints (docs/python-int.md) that runtime.c's descriptor walks read: repr(), ==,
# ordering and hash() of tuples of numbers, strs and None, nested and holding lists and dicts, with
# items past 64 bits, -2**63 and values that fit; exact comparisons with floats and with tuples of
# 64-bit ints; the digits limit; and vars() of objects whose fields are promoting ints, int | None
# and such tuples, also one that a module without the comment made (fixed_pairs).
import sys
from dataclasses import dataclass
from fixed_pairs import swap

ONE = len(sys.argv) - 2  # (1, which the compiler does not know)
BIG = 2 ** 64 * ONE
EDGE = -2 ** 63 * ONE


def pair(a: int, b: int) -> tuple[int, int]:
    return a, b


def nested(n: int) -> tuple[tuple[int, int], int, str]:
    return (n, -n), n * n, "s"


def tagged(n: int, s: str) -> tuple[int, str]:
    return n, s


# repr(), str() and formatting
t = pair(BIG, EDGE)
print(t, repr(t), str(t), f"{t}", "%s" % (t,), format(t), f"{t!r:>0}")
print(nested(BIG), nested(EDGE), nested(3), pair(EDGE + 1, -EDGE), pair(BIG * BIG, -BIG))
print((BIG, [1, BIG], {3: BIG}, None, 1.5, True, "x"), ((BIG, (EDGE, (-BIG, ONE))), "deep"))

# == and !=: promoting ints past 64 bits, -2**63 (its slot and a null Mpz word) and ints that fit
print(t == pair(BIG, EDGE), t != pair(BIG, EDGE), t == pair(BIG + 1, EDGE), t == pair(EDGE, BIG))
print(pair(EDGE, 0) == (EDGE, 0), (EDGE, 0) == pair(EDGE, 0), pair(EDGE, 0) == pair(EDGE + 1, 0))
print(nested(BIG) == ((BIG, -BIG), BIG * BIG, "s"), nested(BIG) == ((BIG, BIG), BIG * BIG, "s"), nested(EDGE) == nested(EDGE))
print((BIG, [1, BIG]) == (BIG, [1, BIG]), (BIG, [1, BIG]) == (BIG, [1, BIG + 1]), (BIG, {3: BIG}) == (BIG, {3: BIG}))
# exactly, with floats: around 2**53, 2**63 and 2**64
fl = (1.8446744073709552e19, 1.0)
print(pair(BIG, 1) == fl, pair(BIG + 1, 1) == fl, fl == pair(BIG, 1), fl != pair(BIG - 1, 1))
print(pair(2 ** 53 + ONE, 0) == (9007199254740992.0, 0.0), pair(2 ** 53, 0) == (9007199254740992.0, 0.0))
print(pair(EDGE, 1) == (-9.223372036854776e18, 1.0), pair(EDGE - 1, 1) == (-9.223372036854776e18, 1.0))
print(pair(-BIG, 1) == (-1.8446744073709552e19, 1), pair(BIG, 2) == (BIG, 2.0), (2.0 ** 70, ONE) == pair(2 ** 70, 1))
# with tuples of 64-bit ints, also from a module that does not opt in, and a tuple[int, ...]
small: tuple[int, int] = (1, 2)
print(pair(1, 2) == small, small == pair(1, 2), pair(BIG, 2) == small, small != pair(1, BIG))
print(swap(pair(EDGE, 5)) == pair(5, EDGE), pair(5, EDGE) == swap(pair(EDGE, 5)), swap(pair(1, 2)) == pair(2, 1))
counted = (1, 2, 3)[: ONE + 1]
print(pair(1, 2) == counted, counted == pair(1, 2), pair(BIG, 2) == counted, pair(1, 2) != counted)

# ordering
print(pair(BIG, 1) < pair(BIG, 2), pair(BIG, 1) < pair(BIG + 1, 0), pair(-BIG, 5) < pair(EDGE, 0), pair(EDGE, 0) < pair(EDGE + 1, 0))
print(pair(BIG, 1) <= pair(BIG, 1), pair(BIG, 1) > pair(BIG, 1), pair(BIG * BIG, 0) >= pair(BIG, 9), pair(EDGE, 9) > pair(-BIG, 9))
print(tagged(BIG, "a") < tagged(BIG, "b"), tagged(BIG, "b") < tagged(BIG, "a"), tagged(EDGE, "z") < tagged(EDGE + 1, "a"))
print(nested(BIG) < nested(BIG + 1), nested(EDGE) < nested(-BIG), nested(-BIG) <= nested(-BIG), nested(3) > nested(EDGE))
print(max(pair(BIG, 1), pair(BIG, 2), pair(-BIG, 3)), min(pair(BIG, 1), pair(EDGE, 2), pair(-BIG, 3)))
print(max(tagged(BIG, "a"), tagged(BIG, "c")), min(nested(BIG), nested(EDGE), nested(0)))

# hash(): CPython's, of every item
print(hash(pair(BIG, 1)), hash(pair(EDGE, -1)), hash(pair(-BIG * BIG, 7)), hash((BIG, None, 1.5, True)))
print(hash(pair(2 ** 61 - 1, 0)) == hash((0, 0)), hash(pair(BIG, 1)) == hash((2 ** 64, 1)), hash(pair(EDGE, 0)) == hash((-2 ** 63, 0)))
print(hash(nested(BIG)) == hash(((BIG, -BIG), BIG * BIG, "s")), hash(tagged(BIG, "k")) == hash(tagged(BIG, "k")), hash(nested(5)) == hash(((5, -5), 25, "s")))

# repr() past CPython's limit for an int's text: its ValueError
huge = 10 ** 5000 * ONE
try:
    print(len(repr(pair(huge, 1))))
except ValueError as e:
    print("ValueError:", str(e)[:40])
try:
    print(nested(huge))
except ValueError as e:
    print("print ValueError:", str(e)[:40])
print(len(repr(pair(10 ** 4299, 1))), len(str(pair(-10 ** 4299, -1))))


# the tuples that compiled code compares, hashes and prints item by item: with an object, a union of
# classes or bytes, and orderings of tuples of other types
class Box:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, o: object) -> bool:
        return isinstance(o, Box) and o.v == self.v

    def __lt__(self, o: "Box") -> bool:
        return self.v < o.v

    def __hash__(self) -> int:
        return hash(self.v)

    def __repr__(self) -> str:
        return f"Box({self.v})"


class Other:
    def __repr__(self) -> str:
        return "Other()"


def either(c: bool) -> Box | Other:
    return Box(BIG) if c else Other()


boxed = (BIG, Box(BIG))
print(boxed, boxed == (BIG, Box(BIG)), boxed < (BIG, Box(BIG + 1)), boxed != (BIG, Box(EDGE)), hash(boxed) == hash((BIG, Box(BIG))))
mixed: tuple[int, Box | Other] = (EDGE, either(False))
print(mixed, (BIG, either(True)), (BIG, b"x"), (BIG, b"x") == (BIG, b"x"), hash((BIG, b"y")) == hash((BIG, b"y")))
print(pair(BIG, 1) < (BIG, 1.5), (BIG + 1, 0.5) > pair(BIG, 9), pair(EDGE, 1) <= (-9.223372036854776e18, 1.0), tagged(BIG, "a") < (BIG, "b", 0))


# vars() and __dict__ of objects whose fields are promoting ints, int | None and tuples of them
@dataclass
class Rec:
    n: int
    m: int | None
    t: tuple[int, int]
    u: tuple[tuple[int, int], int, str]
    s: str


class Obj:
    def __init__(self, n: int, m: int | None) -> None:
        self.n = n
        self.m = m


r = Rec(BIG, -BIG * 3, pair(BIG, EDGE), nested(BIG), "x")
print(vars(r))
print(r.__dict__)
print(vars(Rec(EDGE, None, swap(pair(EDGE, 5)), nested(0), "y")))
print(vars(Obj(-BIG * BIG, BIG + 5)), vars(Obj(EDGE, EDGE)), vars(Obj(7, None)))
r.n = 5
r.m = BIG * BIG
r.t = pair(EDGE, EDGE)
print(vars(r), r)
