class Stack(list[int]):
    pass

class Store:
    def __init__(self):
        self.seen: dict[str, list[int]] = {"old": [0]}

replacement: dict[str, list[int]] = {"new": [2]}

class Child(Store):
    def __init__(self):
        super().__init__()
        self.before: dict[str, list[int]] = self.seen
        self.seen = replacement

store = Child()
plain = Store()
alias: dict[str, list[int]] = store.seen

class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        store.seen["item"] = other
        return isinstance(other, Stack)

value = Stack([1])
print(Probe() == value)
print(alias is replacement, store.seen is replacement, store.before is not replacement)
print(alias["item"] is value, store.before, plain.seen)
value.append(3)
print(alias["item"])
