class Stack(list[int]):
    pass


class Store:
    seen: list[list[int]] = []

    def __init__(self, value):
        self.value = value


first = Store(1)
second = Store("two")
alias: list[list[int]] = first.seen


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        second.seen.append(other)
        return isinstance(other, Stack)


item = Stack([1])
print(Probe() == item)
print(first.value, second.value, alias is second.seen)
print(alias[0] is item, type(first.seen[0]).__name__)
