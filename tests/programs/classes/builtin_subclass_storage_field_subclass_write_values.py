class Stack(list[int]):
    pass

class Store:

    def __init__(self):
        self.seen: list[list[int]] = []

class Child(Store):

    def __init__(self):
        super().__init__()
        self.seen = []
store = Child()

class Probe:

    def __eq__(self, other):
        if other is None:
            return False
        store.seen.append(other)
        return len(other) == 1
print(Probe() == Stack([1]))
