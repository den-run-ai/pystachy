# pystachy: dynamic-any
# A sparse 2x string table would skip the second callback and silently give False.
from typing import Any


class Key:
    def __init__(self, text: str):
        self.text = text
        self.calls = 0
        self.raises = False

    def __hash__(self) -> int:
        return hash(self.text)

    def __eq__(self, other: Any) -> bool:
        self.calls += 1
        if self.raises and self.calls == 2:
            raise ValueError("second comparison")
        return self.calls == 2


# Adapt to each interpreter's string hash. On an eight-slot table the second probe
# revisits the first occupied slot; on a sixteen-slot table it visits an empty slot.
text = ""
for i in range(10000):
    candidate = "probe-" + str(i)
    if hash(candidate) & 255 == 224:
        text = candidate
        break
assert text != ""
key = Key(text)
left: dict[Any, Any] = {key: 1}
right: dict[str, int] = {text: 1}
print("boxed to typed", left == right, key.calls)
key.calls = 0
print("typed to boxed", right == left, key.calls)
key.calls = 0
key.raises = True
try:
    print(left == right)
except ValueError as error:
    print(error, key.calls)
