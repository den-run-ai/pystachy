"""Module for tests/programs/imports/complex_default_left_out.py: defs that annotate a parameter
complex. One whose default value is of another type compiled before complex was a type, left
out; it still is, and its default is still evaluated when the def runs."""


def note(text: str) -> int:
    print("default", text)
    return len(text)


def scaled(x: float, factor: complex = note("factor")) -> complex:
    return x * factor


def shifted(z: complex, by: complex = complex(note("by"), 1)) -> complex:
    return z + by


def plain(z: complex = 0) -> complex:
    return z


def doubled(z: complex) -> complex:
    return z * 2
