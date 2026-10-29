# pystachy: dynamic-any
# A dynamic getattr default is captured before lookup. It retains mutable aliases
# and object identity; exceptions from evaluating it are outside the lookup catch.
from typing import Any


fallback: list[Any] = [1]


class Reader:
    def __init__(self, missing: bool) -> None:
        self.missing = missing

    @property
    def item(self) -> Any:
        global fallback
        print("getter", self.missing)
        fallback = [2]
        if self.missing:
            raise AttributeError("missing")
        return fallback


class Exploding:
    @property
    def item(self) -> Any:
        print("exploding getter")
        raise ValueError("getter error")


def default_value() -> Any:
    print("default")
    return fallback


def receiver(missing: bool) -> Any:
    print("receiver", missing)
    return Reader(missing)


def failed_default() -> Any:
    print("default failed")
    raise AttributeError("default error")


for missing in [False, True]:
    captured: Any = fallback
    result: Any = getattr(receiver(missing), "item", default_value())
    print("captured", result is captured, result is fallback)
    result.append(3)
    print("aliases", len(captured), len(fallback))

number: Any = 5
result = getattr(number, "item", fallback)
print("absent", result is fallback)
result.append(4)
print(fallback)
reader: Any = Reader(False)
try:
    print(getattr(reader, "item", failed_default()))
except AttributeError as error:
    print(error)
finally:
    print("default cleanup")
exploding: Any = Exploding()
try:
    print(getattr(exploding, "item", default_value()))
except ValueError as error:
    print(error)
finally:
    print("getter cleanup")

number = int("1000")


class NumberReader:
    @property
    def item(self) -> Any:
        global number
        number = int("2000")
        noise: list[Any] = [number, "allocate"]
        print("numeric getter", noise)
        raise AttributeError("missing")


numeric_reader: Any = NumberReader()
old_number: Any = number
numeric_result: Any = getattr(numeric_reader, "item", number)
print(numeric_result, old_number, number)
print("numeric identity", numeric_result is old_number, numeric_result is number)
