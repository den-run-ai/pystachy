# pystachy: dynamic-any
# ** of a dict display whose str keys no identifier spells, through Any values: each key is one
# keyword argument, which **kwargs receives, as CPython passes it (#826)
from typing import Any


def g(**kw: int) -> int:
    print(sorted(kw.items()))
    return len(kw)


class C:
    def m(self, n: int, **kw: int) -> int:
        print(n, sorted(kw.items()))
        return len(kw)


f: Any = g
print(f(**{"a-b": 1}))
print(f(**{"a-b": 1, "a": 2, "b": 3}))
x: Any = C()
print(x.m(0, **{"a b": 2, "c": 3}))
print(x.m(*(1,), **{"$x": 4, "1": 5, "": 6}))
print(x.m(2, **{"é": 7, "a.b": 8}))
