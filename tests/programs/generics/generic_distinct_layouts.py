from typing import Generic, Iterable, TypeVar

T = TypeVar("T")


class Payload(Generic[T]):
    def __init__(self, key: T, value) -> None:
        self.key = key
        self.value = value


class Collection(Generic[T]):
    def __init__(self, values: Iterable[T]) -> None:
        self.values = values
        self.next: Collection[T] | None = None


a = Payload(1, 3)
b = Payload(1, "b")
print(a.key, a.value + 2, b.key, b.value.upper())
xs = Collection([1, 2])
ys = Collection((3, 4))
xs.values.append(5)
ys.next = xs
print(xs.values, ys.values, ys.next.values)
