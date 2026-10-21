# pystachy: dynamic-any
# x if c else x, and x := x: the one binding of x either way, whose object the value keeps where
# it becomes an Any value, as CPython's names hold one object (#807)
from typing import Any

x = int("1000")
a: Any = x
flag = bool(int("1"))
y = x if flag else x
b: Any = y
print(a is b, id(a) == id(b))
z = int("3000")
ys: list[Any] = [z, (z := z)]
print(ys[0] is ys[1], id(ys[0]) == id(ys[1]))


def local(f: bool) -> None:
    p = int("4000")
    c: Any = p
    q = p if f else p
    d: Any = q
    w = int("5000")
    ws: list[Any] = [w, (w := w)]
    print(c is d, id(c) == id(d), ws[0] is ws[1])


local(True)
local(False)
