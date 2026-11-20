# Making an object of a class with abstract methods in a statement of its own raises TypeError,
# and what follows it is code after a raise: a template's branch does not compile it for the
# argument types that take that branch (pick(1)'s x + "a"), and a template that always raises
# takes the type its caller expects (#1618 keeps both, where the raise now leaves a block open)
from abc import ABC, abstractmethod


class Half(ABC):
    @abstractmethod
    def f(self) -> int:
        return 0


def pick(x):
    if isinstance(x, int):
        Half()
        return x + "a"
    return x


def boom(x):
    Half()


try:
    print(pick(1))
except TypeError as e:
    print("pick", e)
print(pick("s"))
try:
    y: int = boom(1)
    print(y + 1)
except TypeError as e:
    print("boom", e)
try:
    Half()
    print("not reached")
except TypeError as e:
    print("statement", e)
