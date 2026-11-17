# isinstance(x, (A, B)) narrows x to A | B only where its function does not compile without the
# union. Here a join (r = 0, then r = "big") restarts the first pass, and the next compiles g with
# x as Base: no read of x boxes it (pys_ubox), as the .calls file pins.
class Base:
    def __init__(self, n: int) -> None:
        self.n = n


class A(Base):
    pass


class B(Base):
    pass


class C(Base):
    pass


def g(x: Base, k: int) -> str:
    total = 0
    if isinstance(x, (A, B)):
        for i in range(3):
            total += x.n
    r = 0
    if k > 1:
        r = "big"
        return r.upper() + str(total)
    return str(r) + str(total)


print(g(A(1), 2), g(B(2), 0), g(C(3), 5))
