# error: mutable default <class 'list'> for field xs is not allowed: use default_factory
from dataclasses import dataclass


@dataclass
class D:
    xs: list[int] | None = []  # (CPython: ValueError, use default_factory)


print(D())
