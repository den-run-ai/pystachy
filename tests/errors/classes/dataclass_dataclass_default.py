# error: mutable default <class '__main__.Inner'> for field inner is not allowed: use default_factory
from dataclasses import dataclass


@dataclass
class Inner:
    n: int = 0


@dataclass
class Outer:
    inner: Inner = Inner()
