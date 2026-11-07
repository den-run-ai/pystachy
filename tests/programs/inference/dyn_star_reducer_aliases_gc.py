# pystachy: dynamic-any
# Transient packs retain their object graph, and reconstruction preserves aliases.
from typing import Any


class Payload:
    def __init__(self, data: list[Any], callback: Any) -> None:
        self.data = data
        self.callback = callback


def reduction(prefix: str) -> Any:
    captured: list[str] = [prefix + ":"]

    def callback(value: int) -> str:
        return captured[0] + str(value)

    data: list[Any] = [1, "retained", [2, 3]]
    original: Any = Payload(data, callback)
    return (type(original), [original.data], {"callback": original.callback})


def churn() -> int:
    total = 0
    for i in range(100):
        trash: list[str] = [str(i), str(i + 1), str(i + 2)]
        total += len(trash[1])
    return total


saved: Any = reduction("payload")
print(churn())
factory, args, kwargs = saved
value = factory(*args, **kwargs)
print(type(value) is Payload, value.data is args[0], value.callback is kwargs["callback"])
args[0].append("alias")
print(value.data, value.callback(7))

# Only the result retains the graph after the original packs leave scope.
saved = None
args = None
kwargs = None
print(churn())
print(value.data, value.callback(8))
value.data[2].append(4)
print(value.data)


def identity(a: Any, b: Any) -> Any:
    return (a, b)


call: Any = identity
shared: list[Any] = ["shared"]
pack: Any = [shared]
kwpack: Any = {"b": shared}
result = call(*pack, **kwpack)
print(result[0] is result[1], result[0] is shared)
result[1].append("changed")
print(shared, pack[0], kwpack["b"])
