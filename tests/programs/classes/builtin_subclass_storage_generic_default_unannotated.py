class Stack(list[int]):
    pass

class Store:
    def __init__(self, items: list[list[int]]):
        self.seen = items

def make_store(seed, items=[[0]]) -> Store:
    print(seed)
    if isinstance(items, int):
        return Store([[items]])
    return Store(items)

first = make_store(7)
second = make_store("shared")
third = make_store("explicit", 9)

class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        first.seen.append(other)
        return isinstance(other, Stack)

value = Stack([1])
print(Probe() == value)
print(first.seen is second.seen, first.seen is not third.seen)
print(second.seen[-1] is value, third.seen)
