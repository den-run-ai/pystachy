# pystachy: dynamic-any
# A method call of an Any value finds the method before it evaluates the arguments, as CPython's
# LOAD_ATTR does: a missing method raises AttributeError before an argument that is a local not
# assigned on this path raises UnboundLocalError; a method that exists is called once its
# arguments are evaluated.
from typing import Any


def f(flag: bool) -> None:
    x: Any = 1
    xs: Any = [1, 2]
    if flag:
        y = 2
    try:
        x.missing(y)
    except AttributeError as e:
        print("AttributeError:", e)
    except NameError as e:
        print("NameError:", type(e).__name__)
    try:
        print(xs.count(y))
    except AttributeError as e:
        print("AttributeError:", e)
    except NameError as e:
        print("NameError:", type(e).__name__)


f(False)
f(True)
