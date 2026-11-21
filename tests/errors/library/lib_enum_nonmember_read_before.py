# error: enum class P's nonmember G is not supported after a member and a statement that reads G as the class body runs (a method's default value, annotation or decorator): Pystachy binds a nonmember() before the members
# CPython's default value is the module's G, which the class body reads before it binds its own;
# Pystachy binds a nonmember() before the members, which read it as a class attribute
from enum import Enum, nonmember

G = 1


class P(Enum):
    A = 1

    def f(self, x: int = G) -> int:
        return x

    G = nonmember(7)


print(P.A.f(), P.A.G)
