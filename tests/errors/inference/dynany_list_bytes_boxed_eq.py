# error: cannot compare list[bytes] == list[dyn]
# pystachy: dynamic-any
from typing import Any


class Item:
    def __eq__(self, other: Any) -> bool:
        print("element")
        return True


raw = [b"x"]
boxed: list[Any] = [Item()]
print(raw == boxed)
