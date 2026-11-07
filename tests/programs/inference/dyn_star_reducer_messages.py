# pystachy: dynamic-any
# The runtime binder reports the same signature errors as fixed-shape calls.
from typing import Any

def target(a: int, b: int, /, c: int = 3, *, d: int, e: int) -> int:
    return a + b + c + d + e

function: Any = target
packs: list[Any] = [[], [1], [1, 2], [1, 2, 3, 4], [1, 2, 3, 4]]
keywords: list[Any] = [{}, {}, {}, {}, {"d": 4, "e": 5}]
for index in range(len(packs)):
    try:
        function(*packs[index], **keywords[index])
    except TypeError as error:
        print(str(error))

bad_keywords: list[Any] = [{"a": 1, "b": 2, "d": 3, "e": 4}, {"b": 2, "a": 1}, {"unknown": 1, "a": 2}, {"a": 2, "unknown": 1}, {"c": 3, "d": 4, "e": 5}]
for mapping in bad_keywords:
    args: Any = [1, 2, 3]
    kwargs: Any = mapping
    try:
        function(*args, **kwargs)
    except TypeError as error:
        print(str(error))
