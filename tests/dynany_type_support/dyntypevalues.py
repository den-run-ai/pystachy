# pystachy: dynamic-any
# A module that opts in and hands Any values of many types to a program that does not
# (tests/programs/inference/dynany_type_is_unopted.py): two list layouts, functions,
# generators, iterators and an instance of its own class.
from typing import Any, Iterator


class Point:
    def __init__(self, x: int) -> None:
        self.x = x


def double(x: int) -> int:
    return 2 * x


def triple(x: int) -> int:
    return 3 * x


def count(n: int) -> Iterator[int]:
    for i in range(n):
        yield i


def values() -> dict[str, Any]:
    return {"int": 1, "bool": True, "float": 2.5, "str": "s", "none": None, "ints": [1, 2],
            "mixed": [1, "two"], "dict": {"k": 1}, "tuple": (1, 2), "point": Point(3),
            "double": double, "triple": triple, "gen": count(2), "gen2": count(3),
            "listiter": iter([1]), "listiter2": iter([2, 3]), "tupleiter": iter((1,))}
