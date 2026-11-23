# lists, tuples and dicts of values of object compare as CPython's do, item by item (identity,
# then ==, by what each item holds): == and != with containers of other item types too, in,
# index() and count(), a dataclass's == of such a field, and a list of values of object that a
# value of object holds; lists of objects of two classes, which no descriptor compares, too
from dataclasses import dataclass


class Key:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Key) and other.n == self.n


class Other:
    pass


@dataclass
class Record:
    name: str
    tags: list[object]


def main() -> None:
    a: list[object] = [1, "two", 3.0, None, [4]]
    b: list[object] = [1, "two", 3.0, None, [4]]
    c: list[object] = [1, "two", 3.5]
    print(a == b, a != b, a == c, a != c, [1, 2] == [1, 2.0], a == (1,))
    ints: list[object] = [1, 2, 3]
    print(ints == [1, 2, 3], [1, 2, 3] == ints, ints == [1, 2], ints != [True, 2, 3], ints == [1.0, 2, 3])
    nan = float("nan")
    na: list[object] = [nan]
    print(na == na, na == [nan])
    t1: tuple[object, int] = ("x", 1)
    t2: tuple[object, int] = ("x", 1)
    print(t1 == t2, t1 == ("x", 2), t1 != ("y", 1), t1 == ("x", 1, 2))
    d1: dict[str, object] = {"a": 1, "b": [2]}
    d2: dict[str, object] = {"b": [2], "a": 1}
    d3: dict[str, object] = {"a": 1, "b": [3]}
    print(d1 == d2, d1 == {"a": 1}, d1 != d3, d1 == {"a": 1, "b": 2})
    print(2 in a, "two" in a, 9 in a, None in a, [4] in a, 3 in a, 1.0 in a, Key(1) in [Key(0), Key(1)])
    print(a.index("two"), a.count(1), a.count(1.0), ints.index(3), ints.count(True))
    try:
        print(a.index("zz"))
    except ValueError as e:
        print("ValueError", e)
    x: object = 2
    print(x in [1, 2, 3], x in (1, 2), [1, 2, 3].index(x), [2, 2].count(x), "s" in a)
    keys: list[object] = [Key(1), Key(2)]
    print(Key(2) in keys, keys.index(Key(2)), keys.count(Key(3)), keys == [Key(1), Key(2)])
    r1 = Record("r", [1, "a"])
    r2 = Record("r", [1, "a"])
    print(r1 == r2, r1 == Record("r", [1, "b"]), r1 != r2)
    inner: list[object] = [2, "x"]
    outer: list[object] = [1, inner]
    held: object = outer
    other: object = [1, 2]
    print(held == outer, held == other, held == [1, 2], other == [1, 2], held != outer)
    left: object = [Key(1)]
    right: object = [Other()]
    print(left == right, left == [Key(1)], [Key(1)] == [Other()])


main()
