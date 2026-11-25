class Stack(list[int]):
    pass

shared: list[list[int]] = [[0]]
before: list[list[int]] = shared

class Store:
    def __init__(self, items: list[list[int]] = shared):
        self.seen: list[list[int]] = items

def make_store() -> Store:
    return Store()

first = make_store()
second = Store()
explicit_items: list[list[int]] = [[9]]
explicit_alias: list[list[int]] = explicit_items
third = Store(items=explicit_items)
after: list[list[int]] = first.seen

class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        first.seen.append(other)
        return isinstance(other, Stack)

value = Stack([1])
print(Probe() == value)
print(first.seen is second.seen, before is after, after is shared)
print(shared[-1] is value, third.seen is explicit_alias, third.seen is not shared)
value.append(2)
print(second.seen, before, third.seen)
