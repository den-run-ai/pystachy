class Stack(list[int]):
    pass

class Store:
    def __init__(self, items: list[list[int]]):
        self.seen: list[list[int]] = items
        self.alias: list[list[int]] = items

items: list[list[int]] = [[0]]
early: list[list[int]] = items
other_items: list[list[int]] = [[9]]
store = Store(items)
second = Store(other_items)
late: list[list[int]] = store.seen

class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        store.seen.append(other)
        return isinstance(other, Stack)

value = Stack([1])
print(Probe() == value)
print(early is items, late is items, store.alias is items)
print(items[-1] is value, second.seen is other_items, second.seen is not items)
value.append(2)
print(early[-1], store.alias[-1], second.seen)
