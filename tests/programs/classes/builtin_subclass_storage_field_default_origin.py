class Stack(list[int]):
    pass


values: list[list[int]] = []
before: list[list[int]] = values
other_values: list[list[int]] = []


class Store:
    seen: list[list[int]] = before


class Child(Store):
    seen: list[list[int]] = other_values


first = Store()
second = Store()
child = Child()


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        first.seen.append(other)
        child.seen.append(other)
        return isinstance(other, Stack)


item = Stack([1])
print(Probe() == item)
print(values is before, Store.seen is values, second.seen is values)
print(Child.seen is other_values, child.seen is values)
print(before[0] is item, child.seen[0] is item)
values[0].append(2)
print(child.seen, type(before[0]).__name__)
