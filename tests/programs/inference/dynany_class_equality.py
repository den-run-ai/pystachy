# pystachy: dynamic-any
# A class's equality is metatype equality; the instance's reflected equality runs.
from typing import Any

EVENTS: list[int] = []


class Recognizes:
    def __init__(self, marker: int) -> None:
        self.marker = marker

    def __eq__(self, other: Any) -> bool:
        EVENTS.append(self.marker)
        return other is Recognizes


cls: Any = Recognizes
instance: Any = Recognizes(17)
print(cls is instance, isinstance(cls, Recognizes), isinstance(instance, Recognizes))
print(cls == cls, cls != cls, EVENTS)
print(cls == instance, instance == cls, cls != instance, instance != cls)
print(EVENTS)
# Defining __eq__ without __hash__ affects instances, not the class object key.
registry: dict[Any, str] = {cls: "class"}
print(registry[type(instance)], hash(cls) == hash(type(instance)))
try:
    print(registry[instance])
except TypeError:
    print("unhashable instance")
print(EVENTS)
