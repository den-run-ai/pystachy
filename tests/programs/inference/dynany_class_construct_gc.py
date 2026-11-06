# pystachy: dynamic-any
# A reduction tuple keeps constructor arguments alive; the result then owns them.
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
    return (type(original), (original.data, original.callback))


def churn() -> int:
    total = 0
    for i in range(100):
        trash: list[str] = [str(i), str(i + 1), str(i + 2)]
        total += len(trash[1])
    return total


saved: Any = reduction("payload")
print(churn())
factory, args = saved
value = factory(args[0], args[1])
print(type(value) is Payload, value.data is args[0], value.callback is args[1])
args[0].append("alias")
print(value.data, value.callback(7))

# Drop the tuple's references; only the constructed object retains its contents.
saved = None
args = None
print(churn())
print(value.data, value.callback(8))
value.data[2].append(4)
print(value.data)
