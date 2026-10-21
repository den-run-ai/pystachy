# error: mutable default <class 'dict'> for field counts is not allowed: use default_factory
from dataclasses import dataclass, field


@dataclass
class A:
    counts: dict[str, int] = field(default={}, repr=False)
