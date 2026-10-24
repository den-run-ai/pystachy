# pystachy: dynamic-any
from typing import Any


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


def run() -> None:
    number = int("1000")
    equal = int("1000")
    larger = int("2000")
    xs: list[int] = [larger, number, equal]
    copied = xs.copy()
    built = list(xs)
    sliced = xs[::-1]
    joined = xs + [number]
    repeated = xs * 2
    displayed = [*xs, number]
    collected = [item for item in xs]
    same("copy", copied[1], number)
    same("constructor", built[1], number)
    same("slice", sliced[0], equal)
    same("concat", joined[-1], number)
    same("repeat", repeated[4], number)
    same("starred", displayed[1], number)
    same("comprehension", collected[1], number)
    same("equal distinct", copied[1], copied[2])
    xs.sort()
    same("stable first", xs[0], number)
    same("stable second", xs[1], equal)
    xs.reverse()
    same("reverse", xs[0], larger)
    ordered = sorted(xs)
    same("sorted first", ordered[0], equal)
    same("sorted second", ordered[1], number)
    xs.sort(key=lambda value: -value)
    same("key sort", xs[0], larger)
    same("key stable", xs[1], equal)
    reversed_values = list(reversed(xs))
    same("reversed", reversed_values[0], number)
    index = 0
    for item in xs:
        same("iteration", item, xs[index])
        index += 1
    iterator = iter(xs)
    same("next first", next(iterator), larger)
    same("next second", next(iterator), equal)


run()
