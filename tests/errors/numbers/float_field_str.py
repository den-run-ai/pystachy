# error: expected float | int, got str (note: what is annotated float and was given an int at
# A field annotated float joins the numbers PEP 484 accepts for a float (#1534), an int or a
# bool: no other type
from dataclasses import dataclass


@dataclass
class P:
    x: float


p = P(0)
p.x = "zero"
print(p)
