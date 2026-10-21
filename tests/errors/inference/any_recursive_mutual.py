# error: cannot infer what first() returns: its recursive return type is unresolved; annotate its return type
from typing import Any

def first(n: int) -> Any:
    return second(n)

def second(n: int) -> Any:
    return 1 if n <= 1 else n * first(n - 1)

print(first(5))
