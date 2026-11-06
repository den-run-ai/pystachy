# pystachy: dynamic-any
from typing import Any

def lit(s: str) -> tuple[int, str]:
    return len(s), s


def value(s: str) -> tuple[int, Any]:
    return lit(s)


print(value("ab"))
