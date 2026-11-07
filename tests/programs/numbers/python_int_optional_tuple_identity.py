# pystachy: dynamic-any
# pystachy: python-int
# Optional promoting values enter dynamic tuple storage without narrowing or reboxing.
from typing import Any


def fixed(value: int | None) -> tuple[Any, Any]:
    return (value, (value, value))


def runtime(value: int | None) -> tuple[Any, ...]:
    return (value, value, None)


def check(value: int | None) -> None:
    left = fixed(value)
    right = runtime(value)
    print(value, left[0] is value, left[1][0] is value,
          left[1][0] is left[1][1], right[0] is value,
          right[0] is right[1], right[2] is None)


check(int("5000"))
check(int("1208925819614629174706176"))
check(int("-1208925819614629174706176"))
check(None)
