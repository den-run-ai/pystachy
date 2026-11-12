from typing import Callable


def readers(prefix: str) -> list[Callable[[], list[str]]]:
    return [lambda: row for row in [[prefix + str(i)] for i in range(3)]]


def churn() -> None:
    for i in range(1000):
        values = [str(i) + ":" + str(j) for j in range(8)]
        assert len(values) == 8


first = readers("first:")
second = readers("second:")
churn()
print(first[0](), first[-1](), second[0]())
print(first[0]() is first[-1](), first[0]() is second[0]())
first[0]().append("shared")
churn()
print([f() for f in first], [f() for f in second])


def optional(values: list[str | None]) -> list[Callable[[], str | None]]:
    return [lambda: value for value in values]


print([f() for f in optional(["one", None])])
