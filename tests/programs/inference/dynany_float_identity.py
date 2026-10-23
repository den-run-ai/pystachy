# pystachy: dynamic-any
# Literal floats are one object per exact value in a compiled module. Keep their identity
# through typed variable slots, but do not intern computed floats or merge signed zero.
from typing import Any

import dynfloatmods.a as a
import dynfloatmods.b as b


def show(label: str, x: Any, y: Any) -> None:
    print(label, x is y, x is not y, id(x) == id(y))


def literal() -> Any:
    return 1.5


def another_literal() -> Any:
    return 15e-1


def run() -> None:
    x: Any = 1.5
    show("literal", x, 1.50)
    show("repeated call", literal(), literal())
    show("another function", x, another_literal())
    show("computed", x, float("1.5"))
    show("computed twice", float("1.5"), float("1.5"))
    typed: float = 1.5
    copied = typed
    show("typed literal", typed, x)
    show("typed copy before boxing", copied, x)
    typed = float("1.5")
    show("typed reassignment", typed, x)
    show("negative literal", -1.5, -1.50)
    show("positive zero", 0.0, +0.0)
    show("negative zero", -0.0, -0.00)
    show("signed zero", -0.0, 0.0)
    show("infinity", 1e400, 1e500)
    show("signed infinity", 1e400, -1e400)
    show("computed infinity", 1e400, float("inf"))
    values: list[Any] = [1.5, -1.5, 0.0, -0.0, 1e400, -1e400, 5e-324, 1.7976931348623157e308]
    print("literal values", values)
    nan: Any = float("nan")
    show("one nan", nan, nan)
    show("two nans", nan, float("nan"))
    print("nan equality", nan == nan)
    saved: list[Any] = []
    for _ in range(8):
        saved.append(literal())
        saved.append(float("1.5"))
    show("retained literal", saved[0], saved[-2])
    show("retained computed", saved[1], saved[-1])


run()
global_literal = 1.5
show("typed global", global_literal, literal())
show("one imported module", a.value, a.again())
show("two imported modules", a.value, b.value)
show("main and imported module", literal(), a.value)
