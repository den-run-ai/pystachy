# operator.itemgetter, attrgetter and methodcaller (lib/operator.py, adapted): a getter of
# literal items or names specializes on them, so a fixed tuple's item and an attribute are
# typed statically; getters as sort keys, called directly, stored and passed around
import operator
from operator import attrgetter, itemgetter, methodcaller
from typing import NamedTuple


class Pt(NamedTuple):
    x: int
    y: str


class Inner:
    def __init__(self, v: int) -> None:
        self.v = v

    def twice(self, k: int = 2) -> int:
        return self.v * k


class Person:
    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age
        self.inner = Inner(age)


pairs = [(1, "b"), (3, "a"), (2, "c")]
print(sorted(pairs, key=itemgetter(1)), sorted(pairs, key=itemgetter(0), reverse=True))
counts = {"a": 3, "b": 1, "c": 2}
print(sorted(counts.items(), key=itemgetter(1)), max(counts.items(), key=itemgetter(1)), min(counts.items(), key=itemgetter(1)))
print(itemgetter(0)((5, 6)), itemgetter(-1)((1, 2.5, "last")), itemgetter(True)(("f", "t")))
print(itemgetter(2, 0)((1, "s", 2.5)), itemgetter(0, 1)(["x", "y", "z"]), itemgetter(1, 1)("ab"))
print(itemgetter("b")(counts), itemgetter("c", "a")(counts), itemgetter(1)(Pt(1, "why")))
rows = [("b", 2), ("a", 2), ("c", 1)]
by_second = itemgetter(1)
rows.sort(key=by_second)
print(rows, list(map(itemgetter(0), rows)), [by_second(r) for r in rows])

people = [Person("Ann", 31), Person("Bob", 25), Person("Ção", 40)]
print([p.name for p in sorted(people, key=attrgetter("age"))])
print([p.name for p in sorted(people, key=attrgetter("inner.v"), reverse=True)])
print(attrgetter("name", "inner.v")(people[0]), attrgetter("name")(people[2]))
print(sorted(["b", "A", "c"], key=methodcaller("lower")), methodcaller("split", ",")("a,b"))
print(methodcaller("twice")(Inner(4)), methodcaller("twice", k=5)(Inner(2)), methodcaller("ljust", 5, "*")("ab"))
print(max(people, key=attrgetter("age")).name, methodcaller("twice", 3)(people[1].inner))

# reprs, as C's
print(repr(itemgetter(1)), repr(itemgetter(0, "k")), repr(attrgetter("a", "b.c")))
print(repr(methodcaller("f", 1, "x", y=2.5)), repr(methodcaller("strip")))
print(callable(by_second), isinstance(by_second, operator.itemgetter), isinstance(attrgetter("a"), operator.attrgetter))

# a variable item: lists, strings and dicts take it at run time
def column(i: int) -> list[int]:
    g = itemgetter(i)
    return [g(r) for r in [[1, 2], [3, 4]]]


print(column(0), column(1), [itemgetter(k)({"p": 1, "q": 2}) for k in ["q", "p"]])


class Table:
    def __init__(self) -> None:
        self.key = itemgetter(1)
        self.rows = [(0, "z"), (1, "y")]

    def ordered(self) -> list[tuple[int, str]]:
        return sorted(self.rows, key=self.key)


print(Table().ordered())

# names that are not strings: CPython's TypeError, raised by the constructor
try:
    attrgetter(5)
except TypeError as e:
    print("TypeError:", e)
try:
    methodcaller(5)
except TypeError as e:
    print("TypeError:", e)
try:
    itemgetter(5)([1, 2])
except IndexError as e:
    print("IndexError:", e)
try:
    itemgetter("x")(counts)
except KeyError as e:
    print("KeyError:", e)
