# Widening a loop accumulator retries its caller. Only the final concrete
# keyword-call shape is retained; arguments and the callback still run once.
from typing import Callable

events: list[str] = []


def scale(value):
    events.append(str(value))
    return value * 2.0


callback: Callable[[float], float] = scale


def run(fn: Callable[[float], float], parts: list[float]) -> float:
    total = 0
    for part in parts:
        total += part
    return fn(value=total)


print(run(callback, [0.5, 1.25]), run(callback, []), events)
