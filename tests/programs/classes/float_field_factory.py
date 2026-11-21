# Dataclass fields annotated float whose defaults are ints (#1534): a class-body default,
# field(default=...) and a default_factory (a class, a lambda, a function) that returns an int.
# CPython stores the int, so each such field holds an int | float.
from dataclasses import dataclass, field


def two() -> int:
    return 2


@dataclass
class P:
    a: float = 0
    b: float = field(default=1)
    c: float = field(default_factory=int)
    d: float = field(default_factory=lambda: 3)
    e: float = field(default_factory=two)


@dataclass
class Q:
    a: float = 0.5
    b: float = field(default_factory=float)


p = P()
q = P(0.5, 1.5, 2.5, 3.5, 4.5)
print(p, q, p == P(0.0, 1.0, 0.0, 3.0, 2.0))
print([isinstance(v, int) for v in [p.a, p.b, p.c, p.d, p.e]], [isinstance(v, int) for v in [q.a, q.b, q.c, q.d, q.e]])
print(p.d * 0.5, p.e / 2, q.a - 0.5, Q(), Q(1), Q(1, 2))
