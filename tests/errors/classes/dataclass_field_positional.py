# error: field() takes 0 positional arguments but 1 was given
from dataclasses import dataclass, field


@dataclass
class A:
    n: int = field(3)
