# closed unions: unions of numbers in arithmetic and sorting, ordering, == and in of lists of
# unions, a union holding a class (which may be None, as its objects may), a union | None,
# dicts and tuples as members, bool next to int, mixed displays, and a function whose returns
# have different types
from typing import Optional, Union


class Node:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"Node({self.name})"

    def __eq__(self, other: "Node") -> bool:
        return self.name == other.name


def mean(xs: list[int | float]) -> float:
    t: int | float = 0
    for x in xs:
        t = t + x
    return t / len(xs)


def scale(v: int | float, k: int) -> int | float:
    return v * k


nums: list[int | float] = [3, 1.5, 2, 0.25]
print(nums, sorted(nums), max(nums), min(nums), mean(nums), scale(2, 3), scale(0.5, 3))
print(nums == [3, 1.5, 2, 0.25], nums[1] < nums[0], nums[2] == 2.0, 1 in nums, 1.5 in nums, "x" in [1, "x"])
words: list[int | str] = ["b", "a", "c"]
print(sorted(words), words.index("a"), words.count("b"), words < ["c"])
try:
    print(sorted([1, "a"]))
except TypeError as e:
    print("TypeError:", e)


def label(n: Node | int | None) -> str:
    if n is None:
        return "none"
    if isinstance(n, Node):
        return "node " + n.name
    return f"int {n + 1}"


print(label(Node("x")), label(3), label(None))
items: list[Node | int] = [Node("a"), 2, Node("b")]
print(items, items[0] == Node("a"), items[1] == 2)


def first(xs: list[Optional[Union[int, str]]]) -> str:
    for x in xs:
        if x is not None:
            return str(x)
    return "-"


print(first([None, "q", 1]), first([None]), first([None, None, 5]))
pairs: dict[str, tuple[int, str] | list[int]] = {"t": (1, "one"), "l": [1, 2]}
print(pairs, pairs["t"] == (1, "one"), pairs["l"] != [1, 2])


def walk(x: int | list[int] | dict[str, int]) -> int:
    if isinstance(x, int):
        return x
    if isinstance(x, list):
        return sum(x)
    return sum(x.values())


print(walk(5), walk([1, 2, 3]), walk({"a": 10, "b": 20}))


def bools(x: bool | int | str) -> str:
    if isinstance(x, bool):
        return "bool"
    if isinstance(x, int):
        return "int"
    return "str"


print(bools(True), bools(1), bools(""), isinstance(True, int))


def pick(k):
    if k == 0:
        return 7
    if k == 1:
        return "seven"
    return 7.5


def kind(x):
    v = pick(x)
    if isinstance(v, str):
        return "str " + v
    return "num " + str(v * 2)


print(pick(0), pick(1), pick(2), [pick(i) for i in range(3)], kind(0), kind(1), kind(2))


def stats() -> None:
    mixed = [1, "two", 3.0, [4]]
    total = 0.0
    for m in mixed:
        if isinstance(m, (int, float)):
            total += m
        elif isinstance(m, str):
            total += len(m)
        else:
            total += sum(m)
    print(mixed, total, {"a": 1, "b": "bee"}, [x for x in mixed if not isinstance(x, list)])


stats()
