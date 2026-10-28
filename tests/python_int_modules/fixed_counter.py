# A module that does not opt in to promoting ints, which counts with collections.Counter, whose
# counts are promoting ints in a program where a module opts in
# (tests/programs/numbers/python_int_counter.py).
from collections import Counter


def counted(words: list[str]) -> Counter[str]:
    return Counter(words)


def add_one(c: Counter[str], key: str) -> None:
    c[key] += 1


def doubled(c: Counter[str], key: str):
    # (unannotated: the promoting int that Counter gives, which arithmetic here promotes)
    return c[key] * 2


def keys(c: Counter[str]) -> list[str]:
    return sorted(c)
