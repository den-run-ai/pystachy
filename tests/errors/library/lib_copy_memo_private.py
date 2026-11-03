# error: _memo_put() is lib/copy.py's own: it reads a deep copy's memo back as the original's type
# The memo's helpers read a reference back as the type of the original at hand: called by another
# module, they would read an object of one class as another (B's float field as A's int)
from _pystachy_copy import _Memo, _memo_get, _memo_put


class A:
    def __init__(self) -> None:
        self.n = 4


class B:
    def __init__(self) -> None:
        self.f = 1.0


m = _Memo()
a = A()
_memo_put(m, a, B())
got = _memo_get(m, a)
if got is not None:
    print(got.n)
