# pystachy: dynamic-any
# containers of values of object compared and searched in a program with Any values, whose
# functions take and give their numbers' identity besides: in, index() and count() of a
# list[object] and a tuple, for an object that an Any value holds, the same object stored as
# itself, an int and a str, and == of such lists; also searches that find nothing
from typing import Any


class P:
    def __init__(self, v: int) -> None:
        self.v = v

    def __repr__(self) -> str:
        return f"P({self.v})"


def main() -> None:
    p = P(1)
    a: Any = p
    held: object = a
    typed: object = p
    n: Any = 7
    xs: list[object] = [typed, 7, "s", held]
    print(held in xs, xs.index(held), xs.count(held), typed in xs, xs.count(typed))
    print(7 in xs, xs.index(7), xs.count(7), n in xs, "s" in xs, xs.index("s"))
    print(P(1) in xs, xs.count(8), 8 in xs, 2.5 in xs)
    ys: list[object] = [held]
    print(typed in ys, ys.index(typed), ys.count(p), [held] == [typed], [typed] == [held])
    t: tuple[object, ...] = (held, 7, "s")
    print(typed in t, t.index(7), t.count("s"), t == (typed, 7, "s"))
    try:
        xs.index(P(2))
    except ValueError as e:
        print("ValueError", e)


main()
