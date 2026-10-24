# pystachy: dynamic-any
# Numeric objects survive local storage joins and representation-only narrowing.
from typing import Any


def inferred() -> None:
    x = int("1000")
    values: dict[str, Any] = {"a": x, "b": x, "c": (x := int("2000"))}
    print("joined dict", values["a"] is values["b"], values["c"] is x)
    current: Any = x
    print("joined ids", id(values["a"]) == id(values["b"]), id(values["c"]) == id(current))
    x = float("nan")
    keys: dict[Any, str] = {x: "a", x: "b", (x := float("nan")): "c"}
    print("joined nan keys", len(keys), list(keys.values()))
    items: set[Any] = {x, x, (x := float("nan"))}
    print("joined nan set", len(items), x in items)


def branches(integer: bool) -> None:
    x: int | float
    if integer:
        x = int("1000")
    else:
        x = float("nan")
    y = x
    before: Any = x
    copied: Any = y
    print("copy before boxing", before is copied, id(before) == id(copied))
    if isinstance(x, int):
        narrowed: Any = x
        x = int("1000")
    else:
        narrowed: Any = x
        x = float("nan")
    after: Any = x
    print("narrow and replace", before is narrowed, before is after, id(before) == id(narrowed))
    values: list[Any] = [x, x, (x := int("2000"))]
    print("joined list", values[0] is values[1], values[0] is values[2], values[2] is x)
    for i in range(3):
        x = int("1000") if i % 2 == 0 else float("1.5")
        saved: Any = x
        again: Any = x
        print("loop binding", saved is again, id(saved) == id(again))


def optional(present: bool) -> None:
    x: int | None = int("1000") if present else None
    y = x
    a: Any = x
    b: Any = y
    print("optional copy", a is b, id(a) == id(b))
    if x is not None:
        c: Any = x
        print("optional narrow", a is c, id(a) == id(c))
    x = None
    d: Any = x
    print("optional none", d is None)


def constants_and_zero() -> None:
    x: int | float = 1000
    a: Any = x
    k: Any = 1000
    print("joined integer constant", a is k)
    x = -0.0
    b: Any = x
    z: Any = -0.0
    print("joined float constant", b is z)
    x = float("-0.0")
    values: list[Any] = [x, x, (x := float("0.0"))]
    print("joined zeros", values[0] is values[1], values[0] is values[2], values)
    text: int | str = int("1000")
    first: Any = text
    second: Any = text
    print("scalar union", first is second)
    text = "word"
    third: Any = text
    print("scalar union text", third)


inferred()
branches(True)
branches(False)
optional(True)
optional(False)
constants_and_zero()
