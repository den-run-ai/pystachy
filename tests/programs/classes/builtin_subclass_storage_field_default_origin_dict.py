class Table(dict[str, int]):
    pass


values: dict[str, dict[str, int]] = {}


class Store:
    seen: dict[str, dict[str, int]] = values


class Other:
    seen: dict[str, dict[str, int]] = Store.seen


first = Store()
second = Other()
before: dict[str, dict[str, int]] = second.seen


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        second.seen["item"] = other
        return isinstance(other, Table)


item = Table({"a": 1})
print(Probe() == item)
print(before is values, first.seen is second.seen, Store.seen is Other.seen)
print(before["item"] is item, type(first.seen["item"]).__name__)
values["item"]["b"] = 2
print(second.seen)
