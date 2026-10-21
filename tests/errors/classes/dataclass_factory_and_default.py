# error: cannot specify both default and default_factory
from dataclasses import dataclass, field


@dataclass
class A:
    xs: list[int] = field(default=None, default_factory=list)
