# pystachy: dynamic-any
from typing import Any, Iterator


def same(a: Any, b: Any) -> bool:
    return a is b


def churn() -> None:
    junk = [str(i) for i in range(500)]
    print("churn", len(junk))


def make() -> tuple[float, ...]:
    x = float("nan")
    values: tuple[float, ...] = (x, x, (x := float("nan")), x)
    return values


values = make()
churn()
print("display", same(values[0], values[1]), same(values[1], values[2]), same(values[2], values[3]))

source: Any = float("nan")
query: float = source
items: tuple[float, ...] = (query, query)


def change() -> int:
    global query
    query = float("nan")
    return 0


print("argument order", items.index(query, change()), same(query, source))


def yield_alias(value: float) -> Iterator[float]:
    yield value
    churn()
    yield value


def consume(value: Any) -> tuple[float, ...]:
    typed: float = value
    return tuple(yield_alias(typed))


held = consume(source)
churn()
print("generator", same(held[0], source), same(held[0], held[1]))


def fail() -> float:
    print("failed item")
    raise ValueError("stop")


try:
    partial: tuple[float, ...] = (query, fail(), query)
    print("unexpected", len(partial))
except ValueError as error:
    print(error)
