# pystachy: dynamic-any
# Fresh mixed-list results box items without changing either source's storage.
from typing import Any


numbers: list[int] = [int("1000")]
words: list[str] = ["word"]
mixed = numbers + words
print(mixed, words + numbers)
print(mixed is numbers, mixed is words)
number: Any = numbers[0]
print(mixed[0] is number)
mixed[0] = "changed"
print(numbers, mixed)
numbers.append(7)
print(numbers, mixed)

floats: list[float] = [float("1.25")]
float_item: Any = floats[0]
float_mixed = words + floats
print(float_mixed, float_mixed[1] is float_item)
empty_numbers: list[int] = []
empty_words: list[str] = []
print(empty_numbers + words, numbers + empty_words, empty_numbers + empty_words)


class Item:
    def __init__(self, value: int) -> None:
        self.value = value


objects: list[Item] = [Item(3)]
joined = objects + words
joined[0].value = 8
print(objects[0].value, joined[0] is objects[0])

inner: list[Any] = ["before"]
nested: list[list[Any]] = [inner]
nested_joined = nested + numbers
nested_joined[0].append("after")
print(inner, nested_joined[0] is inner)


def left() -> list[int]:
    print("left")
    return numbers


def right() -> list[str]:
    print("right")
    numbers.append(9)
    return words


print(left() + right())
print((numbers + words) * 2)
