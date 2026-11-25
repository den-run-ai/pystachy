# error: expected list[int], got Stack
class Stack(list[int]):
    pass


class Store:
    def __init__(self, items: list[list[int]]):
        self.seen = items


items: list[list[int]] = []
store = Store(items)


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        store.seen.append(other)
        return isinstance(other, Stack)


print(Probe() == Stack([1]))
