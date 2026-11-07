# pystachy: dynamic-any
# Lookup captures its callback before arguments mutate that same registry slot.
from typing import Any

EVENTS: list[str] = []
REGISTRY: dict[Any, Any] = {}


def original(value: Any) -> str:
    EVENTS.append("original")
    return "old:" + str(value)


def replacement(value: Any) -> str:
    EVENTS.append("replacement")
    return "new:" + str(value)


def mutate() -> Any:
    EVENTS.append("argument")
    REGISTRY[int] = replacement
    return 7


REGISTRY[int] = original
print(REGISTRY[int](mutate()))
print(REGISTRY[int](8))
print(EVENTS)
try:
    REGISTRY[float](mutate())
except KeyError:
    print("missing before argument", EVENTS)
try:
    REGISTRY[int](mutate(), mutate())
except TypeError:
    print("arguments before arity", EVENTS)
