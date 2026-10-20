# pystachy: dynamic-any
# Any globals rebound by functions, closures over Any cells, generators of Any values, and
# augmented assignment of Any items and attributes.
from typing import Any, Iterator

state: Any = 0


def bump() -> None:
    global state
    if isinstance(state, int) and state < 2:
        state = state + 1
    else:
        state = "done"


for _ in range(4):
    bump()
    print(state)


def counter() -> Any:
    count: Any = 0

    def inc(step: Any) -> Any:
        nonlocal count
        count = count + step
        return count
    return inc


inc = counter()
print(inc(1), inc(2.5), inc(-0.5))


def walk(x: Any) -> Iterator[Any]:
    if isinstance(x, list):
        for item in x:
            yield from walk(item)
    else:
        yield x


print(list(walk([1, [2, ["a", [None]]], 3.5])))
d: dict[Any, Any] = {"n": 1, "s": "a"}
d["n"] += 10
d["s"] += "b"
d["l"] = [1]
d["l"] += [2]
print(d)


class Holder:
    def __init__(self) -> None:
        self.v: Any = 1


h: Any = Holder()
h.v += 1
h.v *= 3
print(h.v)
h.v = [h.v]
h.v.append(None)
print(h.v)
xs: Any = [0, 1, 2]
xs[1] += 5
print(xs)
i: Any = 0
while i < 3:
    i += 1
print(i)
acc: Any = None
try:
    acc = 1 / 0
except ZeroDivisionError:
    acc = "caught"
finally:
    print("finally", acc)
