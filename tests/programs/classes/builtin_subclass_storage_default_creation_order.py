events: list[str] = []

class Stack(list[int]):
    pass

def item() -> list[int]:
    events.append("default")
    return [0]

class Store:
    def __init__(self, items: list[list[int]] = [item()]):
        events.append("init")
        self.seen = items

first = Store()
second = Store()
explicit_items: list[list[int]] = [[8]]
third = Store(explicit_items)

class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        first.seen.append(other)
        return isinstance(other, Stack)

value = Stack([1])
print(Probe() == value)
print(events)
print(first.seen is second.seen, third.seen is explicit_items)
print(first.seen[-1] is value, third.seen)
