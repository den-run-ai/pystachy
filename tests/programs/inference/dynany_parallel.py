# pystachy: dynamic-any
# Identity-bearing graphs stay on the ordinary map path.
from typing import Any

try:
    from parallel import map_float
except ImportError:
    from parallel_reference import map_float


def same(x: float) -> float:
    return x


def fresh(x: float) -> float:
    return x + 0.0


def main() -> None:
    x = float("1234.5")
    values = [x]
    shared = map_float(same, values, 4)
    copied = map_float(fresh, values, 4)
    a: Any = shared[0]
    b: Any = copied[0]
    original: Any = x
    print(shared, shared is values, a is original)
    print(copied, copied is values, b is original)


main()
