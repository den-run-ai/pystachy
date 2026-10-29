# pystachy: dynamic-any
from typing import Any


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


def run() -> None:
    first = int("1000")
    equal = int("1000")
    larger = int("2000")
    xs: list[int] = [first, equal, larger]
    seen: list[Any] = []

    def changing(value: int) -> int:
        seen.append(value)
        print("key sees length", len(xs))
        if len(seen) == 1:
            xs.append(int("3000"))
        return -value

    try:
        xs.sort(key=changing)
    except ValueError:
        print("sort mutation")
    same("first key", seen[0], first)
    same("distinct key", seen[1], equal)
    same("last key", seen[2], larger)
    same("restored larger", xs[0], larger)
    same("restored first", xs[1], first)
    same("restored equal", xs[2], equal)
    seen.clear()

    def failing(value: int) -> int:
        seen.append(value)
        if len(seen) == 2:
            raise ValueError("key failed")
        return value

    try:
        xs.sort(key=failing)
    except ValueError:
        print("sort exception")
    same("exception first", seen[0], larger)
    same("exception second", seen[1], first)
    same("exception restored", xs[0], larger)
    same("exception last", xs[-1], equal)


run()
