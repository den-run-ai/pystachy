class Stack(list[int]):
    pass

class Store:
    seen: list[list[int]] = [[8]]

store = Store()
second = Store()
original: list[list[int]] = Store.seen
replacement: list[list[int]] = [[0]]
Store.seen = replacement
shared: list[list[int]] = second.seen
isolated: list[list[int]] = [[3]]
store.seen = isolated

class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        store.seen.append(other)
        return isinstance(other, Stack)

value = Stack([1])
print(Probe() == value)
print(store.seen is isolated, second.seen is replacement, shared is Store.seen)
print(original, shared, isolated[-1] is value)
value.append(2)
print(isolated[-1], original)
