# error: mutable default list[int] for dataclass field 'xs' is not allowed
from dataclasses import dataclass


@dataclass
class A:
    xs: list[int] = []
