# A Callable made from an object's bound method compares equal whatever trait or base it is read
# through, as CPython's bound methods do: the traits' overrides of the root's method share the
# root's family (adapter), and the first trait's comes first (Both, Primary, A, B, Root).
from collections.abc import Callable


class Root:
    def f(self) -> int:
        return 0


class Primary(Root):
    pass


class A(Root):
    def f(self) -> int:
        return 1


class B(Root):
    def f(self) -> int:
        return 2


class Both(Primary, A, B):
    pass


x = Both()
r: Root = x
a: A = x
b: B = x
fr: Callable[[], int] = r.f
fa: Callable[[], int] = a.f
fb: Callable[[], int] = b.f
print(fr(), fa(), fb(), fr == fa, fa == fb, fr == fb)
