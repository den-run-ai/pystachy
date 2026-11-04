# pystachy: dynamic-any
# Mixed concatenation makes a fresh boxed outer list while preserving each
# native int-list element and the checked stores reached through that alias.
from typing import Any


first = int("1000")
equal = int("1000")
second = int("2000")
inner: list[int] = [first]
items: list[list[int]] = [inner]
words = ["word"]
print("original concat", items + words)
forward = items + words
backward = words + items
print("shared inner", forward[0] is inner, backward[1] is inner)

nested: Any = forward[0]
restored: list[int] = nested
print("roundtrip", restored is inner, nested[0] is first)
nested.append(second)
inner[0] = equal
print("shared mutation", items, forward, backward,
      backward[1][0] is equal, nested[1] is second)
backward[1][1] = first
print("dynamic store", inner, forward[0][1] is first)

# The copied outer containers have unrestricted boxed storage. Replacing an
# outer slot does not replace the source's inner list or another alias of it.
forward[0] = "replaced"
forward.append(False)
items.append([second])
print("independent outer", items, forward, backward, backward[1] is inner)


# Consume the typed outer list through an Any receiver. Inner list references
# and their stored integer identities cross unchanged, even on extended slices.
storage: list[Any] = ["left", 0, "right"]
target: Any = storage
target[::2] = items
print("slice aliases", storage[0] is inner, storage[2] is items[1], target[0][0] is equal)
target[0].append(second)
print("slice mutation", items, storage)
pairs: list[tuple[list[int], int]] = [(inner, second)]
target[1:2] = pairs
print("tuple inner", storage[1][0] is inner, storage[1][1] == second)


class Item:
    def __init__(self, value: int) -> None:
        self.value = value


record = Item(9)
records: list[Item | None] = [record, None]
target[:] = records
print("objects", storage[0] is record, storage[0].value, storage[1] is None)
