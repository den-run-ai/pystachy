class Stack(list[int]):
    pass

class Store:
    def __init__(self, items: list[list[int]]):
        self.seen = items

events: list[int] = []

def make_factory(seed: int):
    def make_store(items: list[list[int]] = []) -> Store:
        events.append(seed)
        return Store(items)
    return make_store

make = make_factory(7)
store = make()
second = make()

class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        store.seen.append(other)
        return len(other) == 1

print(Probe() == Stack([1]))
print(store.seen is second.seen, second.seen)
print(events)
