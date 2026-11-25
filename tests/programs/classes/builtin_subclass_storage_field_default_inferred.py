class Stack(list[int]):
    pass


class Store:
    seen = [[0]]


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        Store.seen.append(other)
        return isinstance(other, Stack)


item = Stack([1])
print(Probe() == item)
print(Store.seen, Store.seen[1] is item, type(Store.seen[1]).__name__)
