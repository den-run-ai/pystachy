# Chained comparisons of a hierarchy's objects where one link always raises TypeError (no class
# of the hierarchy defines __le__ or __ge__): the link raises where it runs, after the operands
# before it and nothing after it, also as the first or a middle link and in conditions,
# comprehensions and assertions; where an earlier link is false, the chain is false and the
# raising link never runs. (#908: these did not compile.)
class B:
    def __init__(self, k: int) -> None:
        self.k = k

    def __lt__(self, other: "B") -> bool:
        print("lt", self.k, other.k)
        return self.k < other.k


class S(B):
    pass


def v(o: B) -> B:
    print("operand", o.k)
    return o


def first(x: B, y: B, z: B) -> bool:
    return v(x) <= v(y) < v(z)


def second(x: B, y: B, z: B) -> bool:
    return v(x) < v(y) <= v(z)


def middle(w: B, x: B, y: B, z: B) -> bool:
    return v(w) < v(x) >= v(y) < v(z)


def both(x: B, y: B, z: B) -> bool:
    return v(x) <= v(y) >= v(z)


def in_if(x: B, y: B, z: B) -> str:
    if x < y <= z:
        return "in"
    return "out"


def in_ifexp(x: B, y: B, z: B) -> str:
    return "yes" if not (x < y <= z) else "no"


def in_while(xs: list[B]) -> int:
    i = 0
    while i + 2 < len(xs) and xs[i] < xs[i + 1] <= xs[i + 2]:
        i += 1
    return i


def in_comprehension(xs: list[B], lo: B, hi: B) -> list[int]:
    return [x.k for x in xs if hi < x <= lo]


def in_assert(x: B, y: B, z: B) -> None:
    assert x < y <= z, "not ordered"


one: B = S(1)
two: B = B(2)
three: B = S(3)
for xs in [[one, two, three], [three, two, one]]:
    try:
        print("first", first(xs[0], xs[1], xs[2]))
    except TypeError as e:
        print("first TypeError:", e)
    try:
        print("second", second(xs[0], xs[1], xs[2]))
    except TypeError as e:
        print("second TypeError:", e)
    try:
        print("middle", middle(xs[0], xs[2], xs[1], xs[0]))
    except TypeError as e:
        print("middle TypeError:", e)
    try:
        print("both", both(xs[0], xs[1], xs[2]))
    except TypeError as e:
        print("both TypeError:", e)
    try:
        print("if", in_if(xs[0], xs[1], xs[2]))
    except TypeError as e:
        print("if TypeError:", e)
    try:
        print("ifexp", in_ifexp(xs[0], xs[1], xs[2]))
    except TypeError as e:
        print("ifexp TypeError:", e)
    try:
        print("while", in_while(xs))
    except TypeError as e:
        print("while TypeError:", e)
    try:
        print("comprehension", in_comprehension(xs, xs[1], xs[2]))
    except TypeError as e:
        print("comprehension TypeError:", e)
    try:
        in_assert(xs[0], xs[1], xs[2])
        print("assert passed")
    except AssertionError as e:
        print("AssertionError:", e)
    except TypeError as e:
        print("assert TypeError:", e)
