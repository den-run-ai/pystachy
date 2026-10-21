# pystachy: dynamic-any
# Dict union may run a key's equality/hash methods: invalidate cached user state (#810).
from typing import Any

seen: list[int] = [0]


class Key:
    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        return 1

    def __eq__(self, other: Any) -> bool:
        seen[0] += 1
        return isinstance(other, Key) and self.value == other.value


left: Any = {Key(1): 10}
right: Any = {Key(1): 20}
before = seen[0]
merged = left | right
print(before, seen[0], len(merged), len(left))
before = seen[0]
left |= right
print(before, seen[0], len(left))
# Pair updates hash the incoming key as well as comparing it to the stored key.
before = seen[0]
left |= [(Key(1), 30)]
print(before, seen[0], len(left))
