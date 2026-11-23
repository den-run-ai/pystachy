# an object of a NamedTuple class, which isinstance() finds a tuple, and one of a class that
# derives from list or from dict, stored as object: views of them read them as the tuple, list or
# dict they are, and "%s" % x takes a NamedTuple's fields as the arguments
from typing import NamedTuple


class Point(NamedTuple):
    x: int
    y: str


class Stack(list[int]):
    def top(self) -> int:
        return self[-1]


class Table(dict[str, int]):
    pass


def show(v: object) -> None:
    x: object = v
    if isinstance(x, (list, tuple)):
        print("seq", len(x), x[0], x[-1], 2 in x, x.count(2), list(x), x)
        for item in x:
            print("  item", item)
    elif isinstance(x, dict):
        print("map", len(x), x["a"], x.get("b"), "a" in x, list(x.items()), x)
    else:
        print("other", x)
    print("%s" % x if not isinstance(x, tuple) else "tuple %s/%s" % x)


def main() -> None:
    s = Stack()
    s.append(1)
    s.append(2)
    t = Table()
    t["a"] = 5
    values: list[object] = [Point(2, "p"), s, t]
    for v in values:
        show(v)


main()
