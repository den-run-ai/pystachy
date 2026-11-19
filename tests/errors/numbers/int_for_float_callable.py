# error: expected float, got int (write a float literal like 1.0, or use float())
# A Callable has one signature: an int argument compiles the function it calls directly (#711),
# not the function a Callable holds
from typing import Callable


def half(x: float) -> float:
    return x / 2


f: Callable[[float], float] = half
print(f(3))
