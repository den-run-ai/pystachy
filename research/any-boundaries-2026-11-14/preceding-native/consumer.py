# pystachy: dynamic-any
from typing import Any
from consumer_models import Box, Errors, Producer, Root, is_box, widen
from consumer_observer import observe, same


def main() -> None:
    errors = Errors()
    errors.items["left"].add("missing")
    errors.items["right"].add("invalid")
    producer = Producer(errors)
    print("constructor", producer.count, producer.errors is errors, isinstance(producer, Root))

    box = Box(producer)
    boxed: Any = box
    print("generic", is_box(boxed), is_box(box), type(boxed) is Box, box.get() is producer)

    original: Any = float("nan")
    distinct: Any = float("nan")
    values = box.get().repeat(original)
    first: float = next(values)
    second: float = next(values)
    print("generator", same(first, original), same(second, original), same(first, second))

    optional: list[float | None] = [first, None, second, distinct]
    frozen: tuple[float | None, ...] = tuple(optional)
    copied = optional.copy()
    alias = optional
    alias[0] = distinct
    print("mutation", optional is alias, same(optional[0], distinct), same(frozen[0], original), same(copied[0], original))
    print("search", copied.count(first), frozen.count(first), first in copied, frozen.index(first, 1), frozen.count(None))
    observe("none", frozen[1], None)
    observe("snapshot", frozen[::-1][-1], original)
    observe("list copy", list(frozen)[2], original)

    raw: tuple[float, ...] = tuple(list(box.get().repeat(original)))
    widened = widen(raw)
    print("widen", same(widened[0], original), same(widened[1], raw[0]), same(list(widened)[1], original))
    for value in widened:
        observe("iterate", value, original)


main()
