# Generic classes (typing.Generic, PEP 484; TypeVarTuple, PEP 646): the call that makes an object
# binds the class's type variables from its arguments, matching __init__'s annotations, and they
# type the object's fields and methods (each binding is a specialization, as a class template's)
from typing import Callable, Generic, TypeVar, TypeVarTuple

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")
R = TypeVar("R")
U = TypeVar("U")
Ts = TypeVarTuple("Ts")


class Box(Generic[T]):
    def __init__(self, item: T) -> None:
        self.item = item
        self.history: list[T] = [item]

    def get(self) -> T:
        return self.item

    def put(self, x: T) -> None:
        self.history.append(x)
        self.item = x

    def mapped(self, fn: Callable[[T], U]) -> list[U]:
        # (U is the method's: a template, compiled for each call's function)
        return [fn(x) for x in self.history]

    def __repr__(self) -> str:
        return f"Box({self.item!r}, {len(self.history)})"


class Table(Generic[K, V]):
    # K from the items of a list, V from another argument
    def __init__(self, default: V, keys: list[K]) -> None:
        self.default = default
        self.rows: dict[K, V] = {}
        for k in keys:
            self.rows[k] = default

    def get(self, k: K) -> V:
        return self.rows.get(k, self.default)

    def set(self, k: K, v: V) -> None:
        self.rows[k] = v


class Maybe(Generic[T]):
    # an argument None binds nothing: the other one binds T
    def __init__(self, x: T | None, fallback: T) -> None:
        self.x: T | None = x
        self.fallback = fallback

    def value(self) -> T:
        x = self.x
        return x if x is not None else self.fallback


class Memo(Generic[*Ts, R]):
    # Ts from a function's parameter types, R from its return type
    def __init__(self, fn: Callable[[*Ts], R]) -> None:
        self.fn = fn
        self.name: str = fn.__name__
        self.seen: dict[tuple[*Ts], R] = {}
        self.calls = 0

    def __call__(self, *args: *Ts) -> R:
        if args in self.seen:
            return self.seen[args]
        self.calls += 1
        r = self.fn(*args)
        self.seen[args] = r
        return r


class Apply(Generic[T, R]):
    # T from both the function's parameter and the value
    def __init__(self, fn: Callable[[T], R], x: T) -> None:
        self.result: R = fn(x)
        self.arg: T = x


class Row(Generic[T, *Ts]):
    # *Ts from the extra positional arguments
    def __init__(self, key: T, *cells: *Ts) -> None:
        self.key = key
        self.cells: tuple[*Ts] = cells

    def swap(self, other: tuple[*Ts]) -> tuple[*Ts]:
        old = self.cells
        self.cells = other
        return old

    def whole(self) -> tuple[T, tuple[*Ts]]:
        return (self.key, self.cells)


def area(w: int, h: int) -> int:
    return w * h


def shout(s: str) -> str:
    return s.upper() + "!"


@Memo
def fib(n: int) -> int:
    return n if n < 2 else fib(n - 1) + fib(n - 2)


@Memo
def nothing() -> str:
    return "made once"


def run() -> None:
    b = Box(3)
    b.put(4)
    print(b, b.get() + 1, b.mapped(str), b.mapped(lambda x: x * 0.5))
    s = Box("x")
    s.put("yz")
    print(s, s.get().upper(), s.mapped(len), isinstance(s, Box), isinstance(b, Box))
    boxes = [Box(1), Box(2)]  # (one binding, one specialization: a list holds both)
    boxes.append(b)
    print(boxes, sum([x.get() for x in boxes]))
    t = Table(0, ["a", "b"])
    t.set("c", 7)
    print(t.get("a"), t.get("c"), t.get("zz"), sorted(t.rows))
    u = Table("-", [1, 2, 3])
    print(u.get(2), u.get(9))
    m1 = Maybe(None, 10)
    m2 = Maybe(5, 0)
    print(m1.value(), m2.value(), m1.x, m2.x)
    m = Memo(area)
    print(m(3, 4), m(3, 4), m(2, 5), m.calls, m.name, sorted(m.seen))

    def label(n: int, unit: str) -> str:
        return f"{n} {unit}"

    lm = Memo(label)
    print(lm(2, "kg"), lm(2, "kg"), lm(3, "m"), lm.calls, lm.name)
    print(fib(80), fib.calls, fib(80), fib.calls)
    print(nothing(), nothing(), nothing.calls, nothing.seen)
    a = Apply(shout, "four")
    print(a.result, a.arg)
    r = Row("k", 1, "a", True)
    print(r.cells, r.swap((2, "b", False)), r.cells, r.whole())
    e = Row(0)
    print(e.cells, e.whole())


run()
