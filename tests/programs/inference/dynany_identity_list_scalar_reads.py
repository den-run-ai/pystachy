# pystachy: dynamic-any
from typing import Any

original: Any = float("nan")
values: list[float] = [original]


class Observer:
    def __radd__(self, other: Any) -> int:
        print("reflected arithmetic", other is original)
        return 7

    def __eq__(self, other: Any) -> bool:
        print("reflected comparison", other is original)
        return True


observer: Any = Observer()
print("open arithmetic", values[0] + observer)
print("open comparison", values[0] == observer)
held: Any = values[0]
print("bare read", held is original)
held = (saved := values[0])
print("named expression", held is original)
print("identity", values[0] is original)
print("membership", values[0] in [original])


def index() -> int:
    print("index callback")
    return 0


held = values[index()]
print("callback read", held is original)


class Items:
    @property
    def items(self) -> list[float]:
        print("property callback")
        return values

    def __getitem__(self, i: int) -> float:
        print("getitem callback")
        return values[i]


items = Items()
print("property arithmetic", items.items[0] + observer)
print("protocol arithmetic", items[0] + observer)
number: Any = int("1000")
xs: list[int] = [number, 2]
print("scalar", xs[0] + xs[1], 0 < xs[0] < 2000, xs[True] * 3)
print("scalar float", values[0] == values[0])
held = xs[0]
print("after scalar", held is number)
events: list[str] = []


def later() -> int:
    events.append("later")
    return 1


try:
    print(xs[99] + later())
except IndexError:
    print("first exception", events)
try:
    print(xs[99] + 1 // 0)
except IndexError:
    print("scalar first exception")
try:
    print(xs[99] == 1 // 0)
except IndexError:
    print("comparison first exception")
held = xs[0]
print("after errors", held is number)
