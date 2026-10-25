# pystachy: dynamic-any
"""Private return companions survive aliases and are reset between calls."""
from typing import Any, Callable


def preserve(value: float) -> float:
    return value


def fresh(seed: str) -> float:
    return float(seed)


def make_int(seed: str) -> int:
    return int(seed)


def observe(value: Any, same: Any) -> bool:
    return value is same


def call(fn: Callable[[float], float], value: float) -> float:
    return fn(value)


def main() -> None:
    value: Any = float('nan')
    print(observe(preserve(value), value))
    print(observe(call(preserve, value), value))
    copied = fresh('nan')
    alias = copied
    print(observe(copied, alias))
    numbers: list[Any] = []
    for i in range(3):
        result = fresh('nan')
        numbers.append(result)
        numbers.append(result)
    print(numbers[0] is numbers[1], numbers[2] is numbers[3], numbers[4] is numbers[5])
    print(numbers[0] is numbers[2], numbers[2] is numbers[4])
    integer: Any = make_int('1000')
    converted: Any = float(make_int('1000'))
    print(type(integer).__name__, type(converted).__name__, integer == converted)
    chosen = fresh('nan') if len(numbers) else preserve(value)
    print(observe(chosen, chosen))


main()
