# error: mutable default <class 'set'> for field seen is not allowed: use default_factory
from dataclasses import dataclass


@dataclass
class A:
    seen: set[int] = set()
