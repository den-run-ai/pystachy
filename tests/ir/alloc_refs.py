# allocelide (alloc_refs.calls): only an object or fixed tuple whose every word is an int, a float
# or a bool by the compiler's types comes from pys_new, whose call LLVM may delete (lowering's
# alloc_call and ref_free); one that holds a reference comes from pys_alloc. A hierarchy's class
# word and assignment flags are scalars; a class attribute that the class body declares takes a
# slot of each object, of its type (Vec's, as raytrace's Vector has). The tuples that make_strs and
# make_ints return are made by their tupleret wrappers, which kept() calls (unpacked() takes their
# slots by value). alloc_refs_dyn.py and alloc_refs_big.py hold numeric identity companions and
# promoting ints
from typing import Optional


class Floats:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y


class Named:
    def __init__(self, name: str) -> None:
        self.name = name


class Maybe:
    def __init__(self, v: Optional[int]) -> None:
        self.v = v


class Base:
    def __init__(self, a: int) -> None:
        self.a = a

    def get(self) -> int:
        return self.a


class Scalars(Base):
    def __init__(self, a: int, b: float, c: bool) -> None:
        super().__init__(a)
        self.b = b
        self.c = c

    def get(self) -> int:
        return self.a + 1


class Tagged(Base):
    def __init__(self, a: int, tag: str) -> None:
        super().__init__(a)
        self.tag = tag


class Vec:
    UNIT: "Vec" = None

    def __init__(self, x: float) -> None:
        self.x = x


def floats(x: float) -> Floats:
    return Floats(x, x)


def named(s: str) -> Named:
    return Named(s)


def maybe(v: int) -> Maybe:
    return Maybe(v)


def scalars(a: int) -> Base:
    return Scalars(a, 0.5, True)


def tagged(a: int) -> Base:
    return Tagged(a, "t")


def vec(x: float) -> Vec:
    return Vec(x)


def pair(a: int, b: float) -> list[tuple[int, float]]:
    return [(a, b)]


def labeled(a: int, s: str) -> list[tuple[int, str]]:
    return [(a, s)]


def make_strs(k: int) -> tuple[str, int]:
    return "s" * k, k


def make_ints(k: int) -> tuple[int, int]:
    return k, k + 1


def unpacked(k: int) -> int:
    s, n = make_strs(k)
    a, b = make_ints(k)
    return len(s) + n + a + b


def kept(k: int) -> list[tuple[str, int]]:
    return [make_strs(k)] if make_ints(k)[0] >= 0 and make_ints(k) is not None else []


def sentinels() -> int:
    marks = [object(), object()]
    return len(marks)


Vec.UNIT = Vec(1.0)
print(floats(1.0).x, named("n").name, maybe(2).v, scalars(3).get(), tagged(4).get(), vec(5.0).x)
print(pair(1, 2.0), labeled(3, "x"), unpacked(2), kept(2), sentinels())
