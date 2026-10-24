# pystachy: dynamic-any
from typing import Any


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


def run() -> None:
    first = float("nan")
    second = float("nan")
    xs: list[float] = [first, first]
    same("inserted source", xs[0], first)
    same("repeated item", xs[0], xs[0])
    same("two slots", xs[0], xs[1])
    keys: set[Any] = {xs[0], xs[1], first}
    print("nan keys", len(keys))
    alias = xs
    xs.append(second)
    alias.insert(1, first)
    same("append", xs[-1], second)
    same("insert", xs[1], first)
    xs[0] = second
    same("replacement", alias[0], second)
    same("distinct nan", xs[0], xs[1])
    xs[-1] = xs[1]
    same("item copy", xs[-1], first)
    old: Any = xs[1]
    xs[1] = float("nan")
    same("retired item", old, first)
    same("fresh replacement", xs[1], first)
    xs[1:3] = [first, second, first]
    same("slice first", xs[1], first)
    same("slice second", xs[2], second)
    same("pop", xs.pop(2), second)
    del xs[0]
    del xs[1:2]
    same("after deletion", xs[0], first)
    xs.clear()
    alias.extend([second, first])
    same("clear refill", xs[0], second)
    xs.extend(xs)
    same("self extend", xs[0], xs[2])
    xs *= 2
    same("inplace repeat", xs[0], xs[4])
    xs += [first]
    same("inplace concat", xs[-1], first)
    # The list is the only live owner after the originating binding is replaced.
    held: Any = xs[0]
    retained = id(held)
    held = None
    second = float("nan")
    for i in range(30):
        trash: Any = float(str(i))
    held = xs[0]
    print("list root", retained == id(held))


run()
