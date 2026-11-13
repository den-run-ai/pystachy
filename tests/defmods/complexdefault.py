"""Module for tests/programs/imports/deftime_complex_default.py and its error case."""


def note(s: str) -> int:
    print("note", s)
    return 1


def raw(data: complex = note("raw")) -> float:
    # an int default that CPython keeps although the annotation says complex: the def statement
    # runs it, and only a call that leaves data out is rejected
    return data.real
