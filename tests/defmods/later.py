"""Module for tests/programs/imports/deftime_later.py."""


def check(x, fs=(LATER, ...)):
    "a default value Pystachy cannot compile (Ellipsis): CPython evaluates it, and LATER is unbound"
    return x


LATER = 1
