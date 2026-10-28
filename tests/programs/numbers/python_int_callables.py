# pystachy: python-int
# Promoting ints (docs/python-int.md) as the ints that a Callable takes and returns: lambdas,
# closures, bound methods (also of a class hierarchy), defs and builtins as Callables, in variables,
# fields, lists and dicts, a generic function's, a sort key, a defaultdict's factory and one that
# returns an object of a class template, past 64 bits and -2**63 too (python_int_callables_fixed.py:
# a module that does not opt in).
from collections import defaultdict
from typing import Callable, TypeVar

T = TypeVar("T")
big = 2 ** 70
low = -(2 ** 63)

# a lambda, a closure and a Callable that returns one
f: Callable[[int], int] = lambda x: x * 2
print(f(big), f(3), f(low))


def make(k: int) -> Callable[[int], int]:
    def add(x: int) -> int:
        return x + k
    return add


def adder(k: int) -> Callable[[int], int]:
    return lambda x: x + k


mk: Callable[[int], Callable[[int], int]] = adder
print(make(big)(1), make(1)(big), mk(big)(1), mk(low)(low))


# bound methods, also through a base class whose subclass overrides it
class Acc:
    def __init__(self) -> None:
        self.total = 0

    def add(self, x: int) -> int:
        self.total += x
        return self.total


class Base:
    def scale(self, x: int) -> int:
        return x * 2


class Sub(Base):
    def scale(self, x: int) -> int:
        return x * 3


def pick(i: int) -> Base:
    return Base() if i == 0 else Sub()


a = Acc()
h: Callable[[int], int] = a.add
print(h(big), h(1), a.total)
fs: list[Callable[[int], int]] = [pick(0).scale, pick(1).scale, lambda x: x - 1]
print([g(big) for g in fs], [g(1) for g in fs])


# fields, dicts, int | None and None results, two parameters
class Rule:
    def __init__(self, f: Callable[[int, int], int]) -> None:
        self.f = f

    def run(self, a: int, b: int) -> int:
        return self.f(a, b)


r = Rule(lambda a, b: a * b)
ops: dict[str, Callable[[int, int], int]] = {"add": lambda a, b: a + b, "mul": lambda a, b: a * b}
print(r.run(big, big), r.run(2, 3), ops["add"](big, 1), ops["mul"](low, 2), sorted(ops))
nxt: Callable[[int | None], int | None] = lambda x: None if x is None else x + 1
out: list[int] = []
keep: Callable[[int], None] = lambda x: out.append(x)
keep(big)
keep(low)
print(nxt(None), nxt(big), nxt(1), out)


# a generic function given a Callable, and a Callable as a sort key and for map()
def apply_t(g: Callable[[T], T], x: T) -> T:
    return g(x)


ks: Callable[[int], int] = lambda x: -x
xs = [big, 1, low, 3]
print(apply_t(f, 5), apply_t(f, big), sorted(xs, key=ks), max(xs, key=ks), list(map(ks, xs)))


# a defaultdict's factory: a lambda, a def and a builtin
def zero() -> int:
    return 0


d: defaultdict[str, int] = defaultdict(lambda: big)
e: defaultdict[str, int] = defaultdict(zero)
c: defaultdict[str, int] = defaultdict(int)
e["a"] += big
c["x"] += low
print(d["k"], d["k"] + 1, e["a"], e["b"], sorted(e.items()), c["x"] - 1, c["y"])


# a Callable that returns an object of a class template, whose specialization its type names
class Node:
    def __init__(self, v):
        self.v = v


def build(g: Callable[[int], Node], n: int) -> Node:
    return g(n)


def node2(x: int) -> Node:
    return Node(x * 2)


print(build(lambda x: Node(x * 2), 5).v, build(node2, 3).v, build(lambda x: Node(x), big).v, build(node2, low).v)
