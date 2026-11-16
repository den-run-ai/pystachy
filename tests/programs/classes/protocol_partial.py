# An implementation needs only the methods that calls through the Protocol use; keyword-only
# parameters and defaults pass through; Protocol() raises CPython's TypeError.
from typing import Protocol


class Store(Protocol):
    def get(self, key: str, *, default: int = -1) -> int: ...

    def keys(self) -> list[str]: ...


class Small:
    def __init__(self) -> None:
        self.d = {"a": 1}

    def get(self, key: str, *, default: int = -1) -> int:
        return self.d.get(key, default)


s: Store = Small()
print(s.get("a"), s.get("b"), s.get("b", default=0))
try:
    Store()
except TypeError as e:
    print("TypeError", e)
