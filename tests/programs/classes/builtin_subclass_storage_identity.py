class Stack(list[int]):
    def __eq__(self, other) -> bool:
        print("eq", type(other).__name__)
        return False


s = Stack([1])
items: list[Stack | list[int]] = [s, s, [1]]
print(items[0] is items[1])
print(items[0] == items[1])
print(items[:1] == items[1:2])
print(s in items, items.count(s))
print(items.index(s))
print(items[:1] < items[1:2])
