# pystachy: dynamic-any
# runtime-selected handlers in a registry, called with values of several types
from typing import Any, Callable


def h_int(x: Any) -> Any:
    return x * 2


def h_str(x: Any) -> Any:
    return x.upper()


def h_list(x: Any) -> Any:
    return len(x)


HANDLERS: dict[str, Callable[[Any], Any]] = {"int": h_int, "str": h_str, "list": h_list}
values = [3, "abc", [1, 2, 3], 4]
for v in values:
    print(HANDLERS[type(v).__name__](v))
