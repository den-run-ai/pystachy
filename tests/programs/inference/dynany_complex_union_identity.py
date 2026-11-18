# pystachy: dynamic-any
# Complex objects retain their identity across a closed scalar union and Any, including when
# the same object crosses through a tuple item or a generator. A NaN component makes a lost
# identity visible: it is unequal to itself, but tuple membership still finds the original.
from typing import Any, Iterator


def choose(value: complex) -> int | complex:
    return value


def optional(value: int | complex | None) -> Any:
    return value


def repeat(value: complex) -> Iterator[complex]:
    yield value
    yield value


def check(value: complex) -> None:
    selected = choose(value)
    boxed: Any = selected
    restored: complex = boxed
    again: Any = restored
    print("round trip", boxed is value, restored is value, again is boxed)
    items: Any = (selected,)
    print("tuple", selected in (selected,), (selected,).count(selected), boxed in items, items[0] is value)
    maybe = optional(selected)
    print("optional", maybe is value, optional(None) is None)
    values = repeat(restored)
    first: Any = next(values)
    second: Any = next(values)
    print("typed generator", first is value, second is value)
    dynamic: Any = repeat(restored)
    print("dynamic generator", next(dynamic) is value, next(dynamic) is value)


check(complex(1, 2))
check(complex(float("nan"), 0))
