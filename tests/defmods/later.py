"""Module for tests/programs/imports/deftime_later.py."""


def check(x, fs=(LATER, 1j)):
    "a default value Pystachy cannot compile (complex): CPython evaluates it, and LATER is unbound"
    return x


LATER = 1
