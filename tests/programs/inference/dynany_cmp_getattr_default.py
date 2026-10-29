# pystachy: dynamic-any
# getattr's default lets this comparison run for a scalar as well as a peer.
# The body and default must run even where the other value has no such field.
# No property or explicit exception handler may mask exception-frame discovery.
from typing import Any


def default_value() -> None:
    print("default")


class G:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other) -> bool:
        print("comparison")
        return self.n == getattr(other, "n", default_value())


class Field:
    def __init__(self, n: int) -> None:
        self.n = n


value: Any = G(7)
scalar: Any = 7
peer: Any = Field(7)
print(value == scalar, scalar == value, value != scalar)
print(value == peer, peer == value)
