# error: field total is declared with init=False, it cannot be specified with replace()
from dataclasses import dataclass, field, replace


@dataclass
class P:
    x: int
    total: int = field(init=False, default=0)


print(replace(P(1), total=5))
