# pystachy: dynamic-any
# A store of the same object preserves earlier reads even before their first box.
from typing import Any


def integers(flag: bool) -> None:
    x = int("1000")
    y = int("1000")
    before, result = (x if flag else x), (x := x if flag else y)
    a: Any = before
    b: Any = x
    c: Any = result
    print("int selection", flag, a is b, b is a, id(a) == id(b), c is b)


def floats(flag: bool, text: str) -> None:
    x = float(text)
    y = float(text)
    before, result = (x if flag else x), (x := x if flag else y)
    a: Any = before
    b: Any = x
    c: Any = result
    print("float selection", text, flag, a is b, b is a, id(a) == id(b), c is b)


def alias_copy() -> None:
    x = int("1000")
    before, result = x, (x := (y := x))
    a: Any = before
    b: Any = x
    c: Any = result
    d: Any = y
    print("int alias", a is b, b is a, id(a) == id(b), c is b, d is b)
    f = float("nan")
    first, assigned = f, (f := (g := f))
    p: Any = first
    q: Any = f
    r: Any = assigned
    s: Any = g
    print("NaN alias", p is q, q is p, id(p) == id(q), r is q, s is q)


def replacements() -> None:
    # Both box slots start empty; equal scalar payloads do not imply one object.
    x = int("1000")
    before, result = x, (x := int("1000"))
    a: Any = before
    b: Any = x
    c: Any = result
    print("int replacement", a is b, b is a, id(a) == id(b), c is b)
    f = float("1000.25")
    first, assigned = f, (f := float("1000.25"))
    p: Any = first
    q: Any = f
    r: Any = assigned
    print("float replacement", p is q, q is p, id(p) == id(q), r is q)


integers(True)
integers(False)
floats(True, "1000.25")
floats(False, "1000.25")
floats(True, "nan")
floats(False, "nan")
floats(True, "-0.0")
floats(False, "-0.0")
floats(True, "0.0")
floats(False, "0.0")
alias_copy()
replacements()
