# pystachy: dynamic-any
# Lazy inputs evaluate each keyword once before iteration, keeping the default's object.
from typing import Any, Callable

fallback = int("1000")
original: Any = fallback
ranged: Any = max(range(0), default=fallback)
generated: Any = min((x for x in range(0)), default=fallback)
empty: list[int] = []
listed: Any = max(empty, default=fallback)
print(ranged is original, generated is original, listed is original)

events: list[str] = []


def default_value() -> int:
    events.append("default")
    return fallback


def replace_key() -> Callable[[int], int]:
    global fallback
    events.append("key")
    fallback = int("1000")
    return abs


before: Any = fallback
first: Any = max(range(0), default=default_value(), key=replace_key())
print(first is before, first is fallback, events)
events.clear()
before = fallback
second: Any = min((x for x in range(0)), key=replace_key(), default=default_value())
print(second is before, second is fallback, events)


def local_rebind() -> None:
    value = int("2000")
    expected: Any = value
    result: Any = max(range(0), default=value, key=key_for(value := int("2000")))
    print(result is expected, result is value)


def key_for(value: int) -> Callable[[int], int]:
    return abs


def default_binding() -> None:
    result = max((bound for _ in range(1)), default=(bound := int("3000")))
    print(result, bound)


local_rebind()
default_binding()


def empty_key(first: Any, second: int) -> None:
    return None


def local_list_rebind() -> None:
    value = int("4000")
    expected: Any = None
    items: list[int] = []
    result: Any = max(items, default=value, key=empty_key(expected := value, value := int("4000")))
    print(result is expected, result is value)


def local_dynamic_rebind() -> None:
    value = int("5000")
    expected: Any = None
    items: Any = []
    result: Any = min(items, default=value, key=empty_key(expected := value, value := int("5000")))
    print(result is expected, result is value)


local_list_rebind()
local_dynamic_rebind()
