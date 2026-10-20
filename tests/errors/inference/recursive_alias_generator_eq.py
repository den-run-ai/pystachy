# error: recursive_alias_generator_eq.py:13: error: generator values cannot be compared or printed
# Generators that yield a recursive alias's values cannot be compared, as other generators.
from collections.abc import Iterator

type V = int | list[V]


def walk(v: V) -> Iterator[V]:
    yield v


gens = [walk(1), walk([2])]
print(gens == gens)
