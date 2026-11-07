# pystachy: dynamic-any
# Imported initializers and their ordinary scalar callees compile on demand.
from typing import Any
from registrymods.factory_only import Empty, Imported, events, shared


factories: list[Any] = [Empty, Imported]
print(events)
empty = factories[0]()
first = factories[1]()
second = factories[1]()
print(type(empty) is Empty, type(first) is Imported)
print(first.original is second.original, first.value, second.value)
print(first.data is shared, second.data is shared)
first.data.append("shared")
print(second.data, shared)

number = int("654321")
data: list[Any] = [2, "supplied"]
third = factories[1](number, data=data)
print(third.original is number, third.value, third.data is data)
print(events)
