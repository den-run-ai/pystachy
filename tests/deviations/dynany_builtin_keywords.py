# Documented deviation (docs/dynamic-any.md): in a module that compiles typing.Any as dynamic
# values, a builtin type's method takes keyword arguments through an Any value only where typed
# code takes them (list.sort()'s key and reverse, dict.update()'s): another raises the TypeError
# typed code reports at compile time, where CPython binds them (here it would print
# ['a', 'b,c']). So does a call with keyword arguments of a function value whose type is a
# Callable, which has no parameter names (here CPython would print 3).
# pystachy: dynamic-any
from typing import Any, Callable


def g(a: int, b: int = 0) -> int:
    return a + b


s: Any = "a,b,c"
try:
    print(s.split(sep=",", maxsplit=1))
except TypeError as e:
    print("TypeError:", e)
c: Callable[[int, int], int] = g
f: Any = c
try:
    print(f(1, b=2))
except TypeError as e:
    print("TypeError:", e)
