# Regression: multiplication protocols and lazy failure preserve CPython order.
from math import prod


class Index:
    def __index__(self) -> int:
        print("index")
        return 2


class Repeat:
    def __rmul__(self, value: str) -> str:
        print("rmul", value)
        return value + "!"

    def __index__(self) -> int:
        print("wrong index")
        return 5


class DictRepeat:
    def __rmul__(self, value: dict[str, int]) -> dict[str, int]:
        print("dict rmul")
        return {"x": value["x"] + 1}


class InvalidIndex:
    def __index__(self) -> str:
        return "bad"


print(prod([Index(), Index()], start="ab"))
print(prod([Index()], start=[1, 2]))
print(prod([Repeat(), Repeat()], start="a"))
print(prod([DictRepeat(), DictRepeat()], start={"x": 1}))
try:
    print(prod([InvalidIndex()], start="a"))
except TypeError as error:
    print(error)


def emitted(n: int) -> int:
    print("item", n)
    return n


def start() -> dict[str, int]:
    print("start")
    return {"x": 1}


try:
    prod((emitted(n) for n in [1, 2, 3]), start=start())
except TypeError as error:
    print(error)
try:
    prod(map(emitted, [1, 2, 3]), start=start())
except TypeError as error:
    print(error)
try:
    prod(["x"], start={"a": 1})
except TypeError as error:
    print(error)
try:
    prod([[1]], start={"a"})
except TypeError as error:
    print(error)
values: list[int | str] = [2, "x"]
try:
    prod(values, start="a")
except TypeError as error:
    print(error)
try:
    prod(values, start={"a": 1})
except TypeError as error:
    print(error)
empty: list[Index] = []
print(prod(empty, start="unchanged"))
nullable: list[int | None] = [2, None]
try:
    prod(nullable, start="a")
except TypeError as error:
    print(error)
none_index: Index = None
try:
    prod([none_index], start="a")
except TypeError as error:
    print(error)
