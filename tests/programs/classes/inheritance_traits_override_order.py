# Traits that override the same method of the primary chain's root: CPython's method resolution
# order (Both, Primary, A, B, Root) picks the first trait's, also through a reference typed as
# a trait or as the root, and in a trait's own method that calls it.
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

    def g(self) -> int:
        return self.f() * 10


class Both(Primary, A, B):
    pass


class Other(Primary, B, A):
    pass


def via_root(r: Root) -> int:
    return r.f()


def via_b(b: B) -> int:
    return b.f()


x = Both()
y = Other()
print(x.f(), via_root(x), via_b(x), x.g(), isinstance(x, A), isinstance(x, B))
print(y.f(), via_root(y), via_b(y), y.g(), isinstance(y, A), isinstance(y, B))
print(via_root(Primary()), via_root(A()), via_b(B()))
