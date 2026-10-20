# error: 'x' is a field but has no type annotation
from dataclasses import dataclass, field


@dataclass
class P:
    x = field(default=1)
