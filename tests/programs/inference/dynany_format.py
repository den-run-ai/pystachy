# pystachy: dynamic-any
# format() of an Any value runs its class's __format__, also with an empty spec (f"{m}",
# format(m, ""), "{}".format(m)), as CPython does (#772); a subclass inherits it. Without one, an
# object formats as str() with an empty spec, and the TypeError for another names its class.
# Numbers, strs, None and containers format as typed ones do.
from typing import Any


class Num:
    def __format__(self, spec: str) -> str:
        return "Num:" + spec

    def __str__(self) -> str:
        return "str-Num"


class Sub(Num):
    pass


class P:
    def __str__(self) -> str:
        return "P!"


def show(x: Any, spec: str) -> None:
    try:
        print(repr(f"{x}"), repr(format(x, "")), repr("{}".format(x)), repr(format(x, spec)), repr(f"{x:{spec}}"))
    except TypeError as err:
        print("TypeError:", err)


show(Num(), ">5")
show(Sub(), "x")
show(P(), "")
show(P(), ">5")
show(42, "05d")
show(2.5, ".3f")
show("ab", "^6")
show(True, "")
show(None, "")
show([1, "a"], "")
w: Any = 7
m: Any = Num()
print(f"[{m:>{w}}]", f"{w:>{w}}", "{:x}|{}".format(m, m))
