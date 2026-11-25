class Stack(list[int]):
    pass

class Store:
    def __init__(self, items: list[list[int]] = []):
        self.seen = items

store = Store()
second = Store()

class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        store.seen.append(other)
        return len(other) == 1

print(Probe() == Stack([1]))
print(store.seen is second.seen, second.seen)
