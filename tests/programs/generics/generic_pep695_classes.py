# PEP 695 generic classes, class C[T, *Ts], are classes of Generic[T, *Ts]: construction binds
# the type parameters, or a C[X] annotation or call names them (#307); bounds, constraints
# and defaults only infer, as a TypeVar's do (#409), so values keep their types. Each class's
# type parameters are its own: two classes may both name theirs T, and a module-level T
# (also a variable) stays another name, here and in a generic def's annotations; a method's
# global statement names the module's. A method's own type parameters (def map[U]) make it a
# template, also where a string annotation names them; a dataclass's field may name a
# specialization (Stack[str]).
from dataclasses import dataclass
from typing import Callable, Iterable

T = "a module-level T"


class Stack[T]:
    def __init__(self, items: list[T]) -> None:
        self.items = items

    def push(self, x: T) -> None:
        self.items.append(x)

    def pop(self) -> T:
        return self.items.pop()

    def peek(self) -> T | None:
        if len(self.items) == 0:
            return None
        return self.items[-1]

    def copy(self) -> "Stack[T]":
        out: list[T] = []
        for x in self.items:
            out.append(x)
        return Stack(out)

    def map[U](self, f: Callable[[T], U]) -> "Stack[U]":
        return Stack([f(x) for x in self.items])


class Pair[K, V]:
    def __init__(self, key: K, value: V) -> None:
        self.key = key
        self.value = value

    def swap(self) -> "Pair[V, K]":
        return Pair(self.value, self.key)

    def __repr__(self) -> str:
        return f"Pair({self.key!r}, {self.value!r})"


class Bounded[T: (int, float)]:
    def __init__(self, x: T) -> None:
        self.x = x


class Defaulted[T: int = int]:
    def __init__(self, x: T) -> None:
        self.x = x


class Apply[A, R]:
    def __init__(self, f: Callable[[A], R]) -> None:
        self.f = f

    def __call__(self, a: A) -> R:
        return self.f(a)


class Bag[T]:
    def __init__(self, xs: Iterable[T]) -> None:
        self.xs: list[T] = list(xs)


class Row[*Ts]:
    def __init__(self, *cells: *Ts) -> None:
        self.cells = cells


class Call[*Ts, R]:
    def __init__(self, f: Callable[[*Ts], R], *args: *Ts) -> None:
        self.f = f
        self.args = args

    def run(self) -> R:
        return self.f(*self.args)


class Mixed[T]:
    def __init__(self, a: T, b: T) -> None:
        self.a = a
        self.b = b


@dataclass
class Named:
    name: str
    stack: Stack[str]


def size(s: str) -> int:
    return len(s)


def scale(n: int, f: float) -> float:
    return n * f


class Tagged[T]:
    def __init__(self, x: T) -> None:
        self.x = x

    def retag(self, suffix: str) -> T:
        global T  # (the module's T, here and in shout, not the type parameter)
        T = T + suffix

        def shout() -> str:
            return T.upper()

        print(shout())
        return self.x


def first[T](xs: list[T]) -> T:
    # (in a generic def's annotations, T is its own too)
    return xs[0]


def tops(boxes: list[Stack[int]]) -> list[int]:
    return [b.pop() for b in boxes]


s = Stack([1, 2])
s.push(3)
print(s.pop(), s.peek(), s.copy().items)
e: Stack[str] = Stack([])
e.push("é")
print(e.items, Stack[float]([]).peek())
p = Pair("a", 1)
print(p, p.swap(), Pair[int, str](1, "x"))
print(Bounded("abc").x, Bounded(2.5).x, Defaulted(3).x, Defaulted("not an int").x)
print(Apply(size)("four"))
print(Bag("abc").xs, Bag({1: 2}).xs)
print(Row(1, "a", 2.5).cells, Call(size, "ab").run(), Call(scale, 2, 3.5).run())
print(tops([Stack([1]), Stack([2, 3])]))
m = Mixed(1, 2.5)
print(m.a, m.b, isinstance(m.a, int), isinstance(m.b, float))
print(T, isinstance(s, Stack), isinstance(p, Pair), first(["ü"]))
print(s.map(str).items, s.map(lambda n: n * 0.5).pop())
nm = Named("n", Stack(["x"]))
nm.stack.push("ÿ")
print(nm.name, nm.stack.items)
print(Tagged(7).retag("!"), T, Tagged("ü").x)
