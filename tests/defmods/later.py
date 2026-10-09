"""Module for tests/deftime_later.py."""


def check(x, fs={LATER}):
    "a default value Pystachy cannot compile (a set): CPython evaluates it, and LATER is unbound"
    return x


LATER = 1
