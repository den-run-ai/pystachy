# pystachy: dynamic-any
# pystachy: python-int
# Small and wide integer representations and promoting lists retain exact types.
from typing import Any


def stored_type(value: Any) -> Any:
    return type(value)


def typed_type(value: list[int]) -> Any:
    return type(value)


small = int("7")
wide = int("123456789012345678901234567890")
small_type = stored_type(small)
wide_type = stored_type(wide)
print(small_type is wide_type, small_type is int, wide_type is int)
print(hash(small_type) == hash(wide_type), id(small_type) == id(wide_type))
registry: dict[Any, str] = {int: "integer", bool: "boolean", list: "sequence"}
for value in [small, wide, -wide, True, False]:
    cls = stored_type(value)
    print(cls.__name__, registry[cls], cls is int)
native: list[int] = [small, wide]
boxed: list[Any] = [small, wide, "text"]
print(typed_type(native) is stored_type(boxed), stored_type(native) is list)
print(registry[stored_type(native)], registry[stored_type(boxed)], len(registry))
print(type(wide_type) is type, isinstance(wide_type, type))
