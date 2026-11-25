# A class-body annotation without a default shares the initializer's final field type.
class Stack(list[int]):
    pass


class Store:
    seen: list[list[int]]

    def __init__(self):
        self.seen = []


class Child(Store):
    pass


store = Store()
child = Child()


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        child.seen.append(other)
        return isinstance(other, Stack)


s = Stack([4])
print(Probe() == s)
print(type(child.seen[0]).__name__, child.seen[0] is s, len(store.seen))
store.seen.append([5])
print(child.seen, store.seen, child.seen is store.seen)
