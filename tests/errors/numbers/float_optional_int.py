# error: expected float | None, got int
# A location annotated float holds an int too (#1534); one annotated float | None does not
from dataclasses import dataclass


@dataclass
class P:
    x: float | None = None


print(P(3))
