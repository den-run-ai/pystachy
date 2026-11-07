# pystachy: dynamic-any
# Factory-only instances retain supplied payloads, identities and object graphs.
from typing import Any


class Node:
    def __init__(self, data: list[Any], number: int) -> None:
        self.data = data
        self.number = number


def churn() -> int:
    total = 0
    for i in range(100):
        trash: list[str] = [str(i), str(i + 1), str(i + 2)]
        total += len(trash[1])
    return total


factory: Any = Node
shared: list[Any] = ["shared"]
retained: list[Any] = []
for i in range(40):
    number = int(str(10000 + i))
    data: list[Any] = [number, shared]
    value = factory(data, number)
    data.append(value)
    retained.append(value)

print(churn())
shared.append("kept")
for index in [0, 19, 39]:
    kept = retained[index]
    print(type(kept) is Node, kept.number, kept.number is kept.data[0])
    print(kept.data[1] is shared, kept.data[1], kept.data[2] is kept)
