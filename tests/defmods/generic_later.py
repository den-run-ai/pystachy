"""Module for tests/deftime_generic_later.py."""


class Box[T]:
    "a generic class, uncompiled: its body reads LATER, unbound then"
    size = LATER


LATER = 1
