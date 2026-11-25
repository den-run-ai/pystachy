class Stack(list[int]):
    def __eq__(self, other: list[int]) -> bool:
        print("eq", type(other).__name__)
        return False


s = Stack([1])
items: list[Stack | list[int]] = [s, s, [1], None]
print(items[0] is items[1], items[0] == items[1])
print(items[:1] == items[1:2])
print(s in items, items.count(s), items.index(s))
print(items[0] == items[3], items[3] == items[0])


class Sized(list[int]):
    def __eq__(self, other: list[int]) -> bool:
        return len(other) == 1


values: list[Sized | list[int]] = [Sized([1]), [1], None]
print(values[0] == values[1])
try:
    print(values[0] == values[2])
except TypeError as e:
    print(str(e))
