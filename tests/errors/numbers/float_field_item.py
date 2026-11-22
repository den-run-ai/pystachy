# error: expected float, got float | int (note: what is annotated float and was given an int at
# A float field that is given an int holds an int | float (#1534), but a list[float]'s items
# are floats: containers keep their item type
from dataclasses import dataclass


@dataclass
class P:
    x: float


p = P(3)
xs: list[float] = [1.5]
xs.append(p.x)
print(xs)
