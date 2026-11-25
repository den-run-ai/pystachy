class Table(dict[str, int]):
    pass


class Store:
    seen: dict[str, dict[str, int]] = {}


class Child(Store):
    seen: dict[str, dict[str, int]] = {}


first = Store()
second = Store()
child = Child()
alias: dict[str, dict[str, int]] = first.seen


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        Store.seen["item"] = other
        Child.seen["item"] = other
        return isinstance(other, Table)


item = Table({"a": 1})
print(Probe() == item)
print(alias is Store.seen, first.seen is second.seen)
print(child.seen is Child.seen, child.seen is Store.seen)
print(alias["item"] is item, child.seen["item"] is item)
alias["item"]["b"] = 2
print(child.seen, type(second.seen["item"]).__name__)
