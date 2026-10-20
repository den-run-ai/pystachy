# pystachy: dynamic-any
# A display of a Callable value and functions holds Callables of its type, as in modules that do not
# opt in, where builtin functions cannot become Any values yet (#782, #774).
from collections.abc import Callable
from typing import Any

cb: Callable[[int, int], int] = lambda x, y: x * y
pair = (6, 7)
print(cb(*pair), [g(*pair) for g in [cb, max]], [g(3, 4) for g in [cb, min, cb]])
mixed: Any = [1, "two"]
print(mixed)
