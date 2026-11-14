# A program's own bindings of the name __file__ keep their meaning: a type parameter of a generic
# def, class or alias, a parameter, a comprehension's variable, a class attribute. The module's
# __file__ is what the name reads elsewhere.
import os


def identity[__file__](x: __file__) -> __file__:
    return x


def outer[T](x: T) -> str:
    def inner[__file__](y: __file__, z: T) -> __file__:
        return y

    return str(inner(x, x)) + os.path.basename(__file__)


class Box[__file__]:
    def __init__(self, v: __file__) -> None:
        self.v = v

    def get(self) -> __file__:
        return self.v

    def swap[U](self, u: U) -> tuple[U, __file__]:
        return (u, self.v)


type Pair[__file__] = tuple[__file__, __file__]


def both(p: Pair[int]) -> int:
    return p[0] + p[1]


def show(__file__: str) -> str:
    return __file__.upper()


def comp() -> list[str]:
    return [__file__ for __file__ in ["a", "b"]]


class K:
    __file__ = "class attr"

    def get(self) -> str:
        return self.__file__


print(identity(42), Box("s").get(), Box(1).swap("u"), both((1, 2)), outer(7))
print(show("x"), comp(), K().get(), K.__file__, os.path.basename(__file__))
