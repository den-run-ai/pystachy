# error: inheritance_secondary_override_overlap.py:23: error: secondary bases B and C both declare method 'f' (not supported, also where D overrides it)
# Two secondary bases that declare a method of one name are not supported, also where the class
# overrides it: CPython's bound method d.f is one whatever base it is read through (fb == fc),
# which a Callable made through each base would not be.
from collections.abc import Callable


class A:
    def g(self) -> int:
        return 0


class B:
    def f(self) -> int:
        return 2


class C:
    def f(self) -> int:
        return 3


class D(A, B, C):
    def f(self) -> int:
        return 4


d = D()
b: B = d
c: C = d
fb: Callable[[], int] = b.f
fc: Callable[[], int] = c.f
print(fb(), fc(), fb == fc)
