# pystachy: dynamic-any
# Native and boxed lists have distinct storage descriptors but one Python class.
from typing import Any


def stored_type(value: Any) -> Any:
    return type(value)


def typed_type(value: list[int]) -> Any:
    return type(value)


native: list[int] = [1, 2]
boxed: list[Any] = [1, "two"]
native_type = typed_type(native)
boxed_type = stored_type(boxed)
print(native_type is boxed_type, native_type is list, boxed_type is list)
print(stored_type(native) is native_type, type(native_type) is type)
print(hash(native_type) == hash(boxed_type), id(native_type) == id(boxed_type))
registry: dict[Any, str] = {native_type: "list"}
print(registry[boxed_type], registry[list], len(registry))
registry[stored_type(native)] = "updated"
print(registry[stored_type(boxed)], len(registry))
# Iterating mixed values forces the lookup to read each value's runtime type.
for value in [native, boxed, "text", 7, None]:
    cls = stored_type(value)
    print(cls.__name__, registry.get(cls, "missing"), cls is list)
