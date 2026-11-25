class Stack(list[int]):
    pass

class Store:
    def __init__(self, items: list[list[int]]):
        self.seen = items

def make_store(seed, items: list[list[int]] = []) -> Store:
    print(seed)
    return Store(items)

store = make_store(7)
second = make_store("eight")

class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        store.seen.append(other)
        return len(other) == 1

print(Probe() == Stack([1]))
print(store.seen is second.seen, second.seen)
