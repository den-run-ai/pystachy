# Generic classes (typing.Generic): further constructor annotations that bind the type
# variables. A union of forms binds by the first member that fits, an Iterable[...] after the
# others; Iterable[T] takes an object's __iter__ items; C[K, V] takes a C object's bindings;
# and a lambda, a builtin such as int or list, or an unannotated def, whose signature binds
# nothing, takes the Callable that the context names. An in-place operand takes the target's
# type.
from typing import Callable, Generic, Iterable, Iterator, Self, TypeVar

K = TypeVar("K")
V = TypeVar("V")
T = TypeVar("T")


class Table(Generic[K, V]):
    def __init__(self, src: "Iterable[tuple[K, V]] | dict[K, V] | Table[K, V]" = (), /) -> None:
        self.rows: dict[K, V] = {}
        if isinstance(src, dict):
            for k, v in src.items():
                self.rows[k] = v
        elif isinstance(src, (list, tuple, set)):
            for k, v in src:
                self.rows[k] = v
        else:
            for k in src.keys():
                self.rows[k] = src.rows[k]

    def keys(self) -> list[K]:
        return list(self.rows)

    def __iter__(self) -> Iterator[K]:
        return iter(list(self.rows))

    def __repr__(self) -> str:
        return f"Table({self.rows!r})"


class Bag(Generic[T]):
    def __init__(self, items: Iterable[T] = (), /) -> None:
        self.items: list[T] = []
        for x in items:
            self.items.append(x)

    def __iter__(self) -> Iterator[T]:
        return iter(self.items)

    def __iadd__(self, other: Self) -> Self:
        self.items.extend(other.items)
        return self

    def __repr__(self) -> str:
        return f"Bag({self.items!r})"


class Lazy(Generic[K, V]):
    def __init__(self, make: Callable[[], V] | None = None, /) -> None:
        self.make: Callable[[], V] | None = make
        self.made: dict[K, V] = {}

    def get(self, k: K) -> V:
        if k not in self.made:
            make = self.make
            if make is None:
                raise KeyError(k)
            self.made[k] = make()
        return self.made[k]


class Opt(Generic[T]):
    def __init__(self, x: "list[T] | T | None") -> None:
        self.x = x


class Seeded(Generic[K, V]):
    # V from the dict argument, then int's Callable: the other arguments bind first
    def __init__(self, make: Callable[[], V], seed: dict[K, V]) -> None:
        self.make: Callable[[], V] = make
        self.rows = seed

    def fresh(self, k: K) -> V:
        self.rows[k] = self.make()
        return self.rows[k]


class Mapper(Generic[T, V]):
    def __init__(self, fn: Callable[[T], V]) -> None:
        self.fn: Callable[[T], V] = fn


def zero():
    return 0


def run() -> None:
    # a dict, pairs, another Table: the member that fits binds K and V
    t1 = Table({"a": 1, "b": 2})
    t2 = Table([("c", 3.5)])
    t3 = Table(t1)
    t4: Table[str, list[int]] = Table()
    t5: Table[int, str] = Table({7: "seven"})
    t6 = Table[str, int]((("x", 1), ("y", 2)))
    t7 = Table({("p", 1)})
    t3.rows["z"] = 26
    print(t1, t2, t3, t4, t5, t6, t7)
    # Iterable[T] of objects whose __iter__ steps through their items
    b1 = Bag("xyz")
    b2 = Bag(b1)
    b3 = Bag(t1)
    print(b1, b2, b3, Bag(Bag([1.5, 2.5])))
    # an in-place operand takes the type of the target, as the operand of b1 + Bag() does
    b1 += Bag()
    b1 += Bag("w")
    print(b1)
    # a lambda, builtins and an unannotated def where the context names V
    lazy_int: Lazy[str, int] = Lazy(int)
    lazy_list: Lazy[str, list[str]] = Lazy(list)
    lazy_lambda: Lazy[str, tuple[int, str]] = Lazy(lambda: (1, "one"))
    lazy_def: Lazy[str, int] = Lazy(zero)
    lazy_float = Lazy[int, float](float)
    lazy_none: Lazy[str, int] = Lazy()
    lazy_list.get("a").append("item")
    print(lazy_int.get("a"), lazy_list.get("a"), lazy_lambda.get("q"), lazy_def.get("d"), lazy_float.get(1))
    try:
        lazy_none.get("missing")
    except KeyError as e:
        print("KeyError", e)
    print(Opt([1, 2]).x, Opt("s").x)
    seeded = Seeded(list, {"a": [1]})
    seeded.fresh("b").append(2)
    counted = Seeded(lambda: 7, {1: 0})
    print(seeded.rows, counted.fresh(2), counted.rows)
    sizes: Mapper[str, int] = Mapper(len)
    upper: Mapper[str, str] = Mapper(lambda s: s.upper())
    print(sizes.fn("four"), upper.fn("abc"), [sizes.fn(w) for w in ["a", "bcd"]])


run()


def kind(f) -> str:
    # isinstance(f, type) is decided by the value's static type: a builtin class is a type
    if f is None:
        return "None"
    if isinstance(f, type):
        return f"<class '{f.__name__}'>"
    return "function"


print(kind(int), kind(list), kind(dict), kind(str), kind(len), kind(zero), kind(lambda: 1), kind(None))
