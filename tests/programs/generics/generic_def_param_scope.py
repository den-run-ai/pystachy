# A generic def's type parameters are its body's names (#505), as a generic class's are its
# methods': where the body binds the name again (a local, a parameter, a comprehension's or a
# lambda's) or declares it global, it reads that; a default value reads the module's or the
# enclosing function's; a nested def's annotations name the outer def's, which make the nested
# def a template too.
from collections.abc import Callable

T = 5


def default[T](x: int = T) -> int:
    return x


def local[T](x: T) -> int:
    T = 3
    return T + 1


def param[T](T: int) -> int:
    return T + 1


def module[T](x: T) -> int:
    global T
    return T + 1


def scopes[T](x: T) -> int:
    return [T for T in range(3)][-1] + (lambda T: T * 2)(4)


def outer[T](x: T) -> list[T]:
    def inner(y: T) -> list[T]:
        return [y, y]

    return inner(x)


def twice[U](u: U) -> list[U]:
    def again[T](t: T) -> list[T]:
        return [t, t]

    return again(u) + again(u)


def enclosing(T: int) -> list[int]:
    # (an enclosing function's T: what a plain nested def reads, and a generic one's default)
    def plain(y: int) -> int:
        return T + y

    def rebinds[T](y: T, z: int = T) -> int:
        T = 3
        return T + z

    def nested[T](y: T) -> int:
        def deeper() -> int:
            return 7

        return deeper()

    return [plain(1), rebinds("a"), nested(2.5)]


def adder[T](x: T) -> Callable[[T], list[T]]:
    def add(y: T) -> list[T]:
        return [x, y]

    return add


class Box:
    def __init__(self, v: int) -> None:
        self.v = v

    def pair[U](self, u: U) -> list[U]:
        def two(w: U) -> list[U]:
            return [w, w]

        return two(u)


print(default(), local(1), param(2), module("x"), scopes(1.5))
print(outer(1), outer("a"), twice(2.5), T)
add_one = adder(1)
add_s = adder("s")
print(enclosing(9), add_one(2), add_s("t"), add_one(3))
print(Box(1).pair("b"), Box(2).pair(4))
