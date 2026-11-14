# Tuples of objects compare as CPython's tuplerichcompare does: each pair of items with == (an
# item is equal to itself without __eq__), the items both tuples have even where their lengths
# differ, then the lengths; ordering compares the first unequal pair with the operator
class K:
    def __init__(self, x: int) -> None:
        self.x = x

    def __repr__(self) -> str:
        return f"K{self.x}"

    def __eq__(self, other: object) -> bool:
        print("eq", self, other)
        return isinstance(other, K) and other.x == self.x

    def __lt__(self, other: "K") -> bool:
        print("lt", self, other)
        return self.x < other.x

    def __le__(self, other: "K") -> bool:
        print("le", self, other)
        return self.x <= other.x

    def __hash__(self) -> int:
        return self.x


class Never:
    def __eq__(self, other: object) -> bool:
        print("never eq")
        return False


class Boom:
    def __eq__(self, other: object) -> bool:
        raise ValueError("no comparison")


def ks(xs: list[int]) -> tuple[K, ...]:
    return tuple(K(x) for x in xs)


a = ks([1, 2, 3])
b = ks([1, 2, 4])
print("same", a == a)
print("equal", a == ks([1, 2, 3]))
print("differ", a == b)
print("longer", a != ks([1, 2]))
print("shorter", ks([1]) == a)
print("lt", a < b)
print("le prefix", ks([1, 2]) <= a)
print("index", a.index(K(2)))
print("count", a.count(K(3)))
n: tuple[Never, ...] = (Never(), Never())
print("identity", n == n, n[0] == n[0])
copy: tuple[Never, ...] = (n[0], n[1])
print("items", n == copy)
boom: tuple[Boom, ...] = (Boom(), Boom())
other: tuple[Boom, ...] = (Boom(),)
try:
    print(boom == other)
except ValueError as e:
    print("ValueError:", e)
