class Stack(list[int]):
    pass

class Store:
    def __init__(self, items: list[list[int]]):
        self.seen = items

events: list[int] = []

def make_factory(seed: int):
    original: list[list[int]] = [[seed]]
    def make_store(items: list[list[int]] = original) -> Store:
        events.append(seed)
        return Store(items)
    return make_store, original

left, left_alias = make_factory(7)
right, right_alias = make_factory(9)
first = left()
second = left()
third = right()
explicit: list[list[int]] = [[4]]
explicit_alias: list[list[int]] = explicit
fourth = right(explicit)

class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        first.seen.append(other)
        return isinstance(other, Stack)

value = Stack([1])
print(Probe() == value)
print(first.seen is second.seen, first.seen is left_alias)
print(third.seen is right_alias, left_alias is not right_alias)
print(fourth.seen is explicit_alias, fourth.seen is not right_alias)
print(left_alias[-1] is value, events)
value.append(2)
print(second.seen, third.seen, fourth.seen)
