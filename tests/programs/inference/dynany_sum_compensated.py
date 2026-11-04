# pystachy: dynamic-any
# Cancellation must agree across boxed lists, Any iterables and streamed items.
from typing import Any


def check(label: str, xs: list[Any]) -> None:
    obj: Any = xs
    print(label, sum(xs), sum(obj), sum(x for x in xs))
    print("float start", sum(xs, 0.0), sum(obj, 0.0), sum((x for x in xs), 0.0))


check("cancel", [1e16, 1.0, -1e16])
check("mixed", [1e16, 1, -1e16])
check("bool", [1e16, True, 1.0, -1e16])
check("int phase", [10, True, 1e16, 1.0, -1e16])
check("empty", [])
check("infinite", [float("inf"), 1.0])
check("nonfinite", [float("inf"), -float("inf")])
check("overflow", [1e308, 1e308])

empty: list[Any] = []
integer: Any = int("1000")
floating: Any = float("1.25")
boolean: Any = True
print("empty identities", sum(empty, integer) is integer, sum(empty, floating) is floating, sum(empty, boolean) is boolean)
values: list[Any] = [1e16, 1.0, -1e16]
print("bool start", sum(values, boolean))
print("signed zero", sum(empty, -0.0), sum((x for x in empty), -0.0))
try:
    print(sum(empty, ""))
except TypeError as err:
    print(type(err).__name__, err)


class FloatResult:
    def __radd__(self, other: Any) -> Any:
        print("radd", other)
        return 1e16


# An int-phase callback returning float enters compensation. A float-phase
# callback receives the compensated value and permanently leaves that phase.
check("enter float", [FloatResult(), 1.0, -1e16])
check("leave float", [1e16, 1.0, -1e16, FloatResult(), 1.0, -1e16])


def stream() -> Any:
    for x in [1e16, 1.0, -1e16]:
        print("yield", x)
        yield x


print("streamed", sum(stream()))


class ObserveStart:
    def __radd__(self, other: Any) -> Any:
        print("start identity", other is observed_start)
        return 1.0


callback_items: list[Any] = [ObserveStart()]
callback_object: Any = callback_items
starts: list[Any] = [integer, floating, boolean]
for observed_start in starts:
    print("callback start", sum(callback_items, observed_start), sum(callback_object, observed_start), sum((x for x in callback_items), observed_start))
