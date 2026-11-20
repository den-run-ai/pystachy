# error: narrow other operations first (note: what is annotated float and was given an int at
# A float field that is given an int holds an int | float (#1534), with a numeric union's
# operations: ** is none of them, and the error names the int that widened the field
from dataclasses import dataclass


@dataclass
class P:
    x: float


p = P(3)
print(p.x ** 2)
