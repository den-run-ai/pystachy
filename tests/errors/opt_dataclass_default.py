# error: mutable default list[int] for dataclass field 'xs' is not allowed
from dataclasses import dataclass


@dataclass
class D:
    xs: list[int] | None = []  # (CPython: ValueError, use default_factory)


print(D())
