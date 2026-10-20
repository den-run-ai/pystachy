# error: non-default argument 'b' follows default argument 'a'
from dataclasses import dataclass, field


@dataclass
class C:
    a: list[int] = field(default_factory=list)
    skipped: int = field(init=False)
    b: int
