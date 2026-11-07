# pystachy: dynamic-any
# A registry retains a closure's only reference to its captured heap payload.
from typing import Any

REGISTRY: dict[Any, Any] = {}


def install(cls: Any, prefix: str) -> None:
    payload: list[str] = [prefix + ":"]

    def reduce(value: Any) -> str:
        return payload[0] + str(value)

    REGISTRY[cls] = reduce


def churn() -> int:
    total = 0
    for i in range(100):
        trash: list[str] = [str(i), str(i + 1), str(i + 2)]
        total += len(trash[1])
    return total


install(int, "number")
install(str, "text")
install(type(None), "empty")
print(churn())
for value in [3, "hello", None]:
    print(REGISTRY[type(value)](value))
old: Any = REGISTRY[int]
install(int, "replacement")
print(churn())
print(old(4), REGISTRY[int](5), REGISTRY[str]("world"))
print(type(None) in REGISTRY, type(type(None)) is type)
