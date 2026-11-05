# The direct pure callback may become a worker; all other callbacks stay serial.
from parallel import map_float


def polynomial(x: float) -> float:
    y = x * x + 0.25
    if x < 0.0:
        return -y
    return y


def mapped(values: list[float], workers: int) -> list[float]:
    return map_float(polynomial, values, workers)


print(mapped([1.0, -1.0, 0.0], 2))
