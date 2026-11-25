class Stack(list[int]):
    pass

class Store:
    def __init__(self, items: dict[str, list[int]]):
        self.seen = items

shared: dict[str, list[int]] = {"old": [0]}

def make_store(items: dict[str, list[int]] = shared) -> Store:
    return Store(items)

first = make_store()
second = make_store()
explicit_items: dict[str, list[int]] = {"own": [9]}
alias: dict[str, list[int]] = explicit_items
third = make_store(explicit_items)

class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        first.seen["item"] = other
        return isinstance(other, Stack)

value = Stack([1])
print(Probe() == value)
print(first.seen is second.seen, second.seen is shared, first.seen["item"] is value)
print(third.seen is alias, alias is not shared)
value.append(2)
print(second.seen, third.seen)
