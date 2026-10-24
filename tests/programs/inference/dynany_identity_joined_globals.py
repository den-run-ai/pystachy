# pystachy: dynamic-any
from typing import Any
import mods.dynidentity_joined_globals as source
from mods.dynidentity_joined_globals import VALUE as IMPORTED

VALUE: int | float | str | None = int("1000")
OPTIONAL: float | None = float("nan")


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


def replace() -> Any:
    global VALUE
    VALUE = int("1000")
    return VALUE


old: Any = VALUE
same("repeated global", VALUE, VALUE)
same("global copy", old, VALUE)
same("optional NaN", OPTIONAL, OPTIONAL)
same("imported union", IMPORTED, source.VALUE)
same("import repeated", source.VALUE, source.VALUE)
same("callback snapshot", VALUE, replace())
same("old snapshot", old, VALUE)
same("after callback", VALUE, VALUE)
source.replace()
same("import retains old", IMPORTED, source.VALUE)
same("import after callback", source.VALUE, source.VALUE)
VALUE = None
same("None", VALUE, None)
VALUE = float("-0.0")
saved: Any = VALUE
same("float copy", saved, VALUE)
VALUE = float("-0.0")
same("equal distinct floats", saved, VALUE)
VALUE = "label"
same("string member", VALUE, VALUE)
OPTIONAL = None
same("optional None", OPTIONAL, None)


def narrow() -> None:
    global VALUE
    VALUE = float("nan")
    if isinstance(VALUE, float):
        a: Any = VALUE
        same("narrowed global", a, VALUE)
    VALUE = int("2000")
    if isinstance(VALUE, int):
        b: Any = VALUE
        same("narrowed integer", b, VALUE)


narrow()


def retain() -> int:
    global VALUE
    VALUE = int("4000")
    observed: Any = VALUE
    return id(observed)


before = retain()
for i in range(40):
    garbage: list[Any] = [int(str(i + 1000)), float(str(i)), "churn"]
after: Any = VALUE
print("global box survives GC", before == id(after))
