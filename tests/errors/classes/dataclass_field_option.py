# error: field(repr=...) needs True or False
from dataclasses import dataclass, field

SHOW = False


@dataclass
class A:
    n: int = field(default=3, repr=SHOW)
