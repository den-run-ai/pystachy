# Unsafe, indirect and unsupported call forms keep ordinary sequential behavior.
from typing import Callable

try:
    from parallel import map_float
except ImportError:
    from parallel_reference import map_float

seen: list[float] = []
events: list[str] = []
live: list[float] = [1.0, 2.0, 3.0]
factor = 2.0


def score(x: float) -> float:
    return x * x + 0.5


def visit(x: float) -> float:
    seen.append(x)
    return x + 1.0


def fail(x: float) -> float:
    seen.append(x)
    if x == 2.0:
        raise ValueError("second")
    return x + 1.0


def grow(x: float) -> float:
    if x == 1.0:
        live.append(4.0)
    return x + 1.0


def shrink(x: float) -> float:
    if x == 1.0:
        live.pop()
    return x + 1.0


def global_read(x: float) -> float:
    return x * factor


def helper(x: float) -> float:
    return score(x)


def divide(x: float) -> float:
    return 1.0 / x


def nested(x: float) -> float:
    values = map_float(score, [x, x + 1.0], 2)
    return values[0] + values[1]


def indirect(fn: Callable[[float], float], values: list[float]) -> list[float]:
    return map_float(fn, values, 4)


def closed(values: list[float], bias: float) -> list[float]:
    def add(x: float) -> float:
        return x + bias

    return map_float(add, values, 4)


def source() -> list[float]:
    events.append("values")
    return [1.0, 2.0]


def workers() -> int:
    events.append("workers")
    return 4


def invalid_workers() -> int:
    events.append("invalid-workers")
    return 0


class Callback:
    def __init__(self, fn: Callable[[float], float]) -> None:
        self.fn = fn


def replace_callback(callback: Callback) -> list[float]:
    callback.fn = global_read
    return [1.0, 2.0]


def main() -> None:
    print("ordered", map_float(visit, [3.0, 1.0, 2.0], 4), seen)
    seen.clear()
    try:
        map_float(fail, [1.0, 2.0, 3.0], 4)
        assert False
    except ValueError as exc:
        print("first-error", str(exc), seen)

    print("grow", map_float(grow, live, 4), live)
    live[:] = [1.0, 2.0, 3.0]
    print("shrink", map_float(shrink, live, 4), live)
    print("global", map_float(global_read, [1.0, 2.0], 4))
    print("helper", map_float(helper, [1.0, 2.0], 4))
    try:
        map_float(divide, [1.0, 0.0, 2.0], 4)
        assert False
    except ZeroDivisionError:
        print("division", "ZeroDivisionError")
    print("nested", map_float(nested, [1.0, 2.0], 4))
    print("indirect", indirect(score, [1.0, 2.0]))
    print("closure", closed([1.0, 2.0], 3.0))
    print("keyword", map_float(workers=4, values=[1.0, 2.0], fn=score))
    print("evaluation", map_float(score, source(), workers()), events)
    events.clear()
    print("keyword-order", map_float(workers=workers(), fn=score, values=source()), events)
    events.clear()
    try:
        map_float(score, source(), invalid_workers())
        assert False
    except ValueError:
        print("validation-order", events)
    callback = Callback(score)
    print("captured-callback", map_float(callback.fn, replace_callback(callback), 4))
    print("replaced-callback", map_float(callback.fn, [1.0, 2.0], 4))
    cases: list[list[float]] = [[], [1.0]]
    for count in [-1, 0, 65]:
        seen.clear()
        for values in cases:
            try:
                map_float(visit, values, count)
                assert False
            except ValueError:
                print("invalid-workers", count, len(values), len(seen))


main()
