# A trait that a class's primary base has comes before the class's own traits in CPython's method
# resolution order (Derived, Combined, Primary, A, B, Root): A's method, which Derived inherits
# through Combined, is not replaced by B's. B's comes before Root's where A has none, and the
# primary chain's own before both, also through a third class statement.
class Root:
    def f(self) -> int:
        return 0

    def g(self) -> int:
        return 0

    def h(self) -> int:
        return 0


class Primary(Root):
    def h(self) -> int:
        return 5


class A(Root):
    def f(self) -> int:
        return 1

    def h(self) -> int:
        return 6


class B(Root):
    def f(self) -> int:
        return 2

    def g(self) -> int:
        return 3


class C(Root):
    def f(self) -> int:
        return 7

    def g(self) -> int:
        return 8


class Combined(Primary, A):
    pass


class Derived(Combined, B):
    pass


class Third(Derived, C):
    pass


def via_root(r: Root) -> str:
    return f"{r.f()} {r.g()} {r.h()}"


def via_b(b: B) -> str:
    return f"{b.f()} {b.g()}"


for o in [Combined(), Derived(), Third()]:
    print(type(o).__name__, o.f(), o.g(), o.h(), via_root(o))
print(via_b(Derived()), via_b(Third()))
