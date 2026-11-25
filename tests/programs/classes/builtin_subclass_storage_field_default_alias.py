class Stack(list[int]):
    pass


class Store:
    seen: list[list[int]] = []


class Child(Store):
    pass


first = Store()
second = Store()
child = Child()
class_alias: list[list[int]] = Store.seen
instance_alias: list[list[int]] = first.seen


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        class_alias.append(other)
        return isinstance(other, Stack)


item = Stack([1])
print(Probe() == item)
print(class_alias is instance_alias, first.seen is second.seen)
print(child.seen is Store.seen, Child.seen is Store.seen)
print(first.seen[0] is item, type(second.seen[0]).__name__)
instance_alias[0].append(2)
child.seen.append([3])


def later() -> None:
    alias: list[list[int]] = Child.seen
    print(alias is class_alias, alias[0] is item, alias)


later()
