# A specialized helper adds no Python frame. Both target and closure paths recurse
# through two source functions per level, and a caught overflow restores the depth.
import sys
from collections.abc import Callable


def kernel(callback: Callable[[int], int], n: int) -> int:
    result = 0
    for _ in range(1):
        result += callback(n)
    return result


def step(n: int) -> int:
    if n == 0:
        return 0
    return kernel(selected, n - 1) + 1


def fallback(unit: int) -> Callable[[int], int]:
    def callback(n: int) -> int:
        if n == 0:
            return 0
        return kernel(selected, n - unit) + unit
    return callback


selected: Callable[[int], int] = step
callbacks: list[Callable[[int], int]] = [step, fallback(1)]
original = sys.getrecursionlimit()
sys.setrecursionlimit(100)
for callback in callbacks:
    selected = callback
    print(kernel(selected, 45))
    try:
        print(kernel(selected, 500))
    except RecursionError:
        print("caught")
    print(kernel(selected, 45))
sys.setrecursionlimit(original)
print(sys.getrecursionlimit() == original)
