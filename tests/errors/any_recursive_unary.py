# error: cannot infer what negate() returns: its recursive return type is unresolved; annotate its return type
from typing import Any

def negate(n: int) -> Any:
    return 1 if n <= 1 else -negate(n - 1)

print(negate(5))
