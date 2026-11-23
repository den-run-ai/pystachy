# The function as a value: calls through it pass the default's literal, or their own.
from typing import Callable


def repair(s: str, logging: bool = False):
    fixed = s.strip()
    if logging:
        return fixed, ["stripped"]
    return fixed


def apply(fn, x):
    return fn(x)


def apply_typed(fn: Callable[[str], str], x: str) -> str:
    return fn(x)


f = repair
print(f(" a "), f(" b ", True))
print(apply(repair, " c "))
print(apply_typed(repair, " d "))
print(list(map(repair, [" e ", " f "])))
print(sorted([" h", "g "], key=repair))
