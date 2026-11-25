class Stack(list[int]):
    pass

class Store:
    def __init__(self):
        self.seen: list[list[int]]
        self.alias: list[list[int]]
        self.alias = self.seen = [[0]]

store = Store()
second = Store()
early: list[list[int]] = store.alias

class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        store.seen.append(other)
        return isinstance(other, Stack)

value = Stack([1])
print(Probe() == value)
print(early is store.seen, store.alias is store.seen, second.seen is not store.seen)
print(early[-1] is value, second.seen)
value.append(2)
print(store.alias[-1])
