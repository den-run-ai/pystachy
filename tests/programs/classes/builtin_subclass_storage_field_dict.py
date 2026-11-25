# A fresh dictionary field preserves a stored dict subclass and its aliases.
class Table(dict[str, int]):
    pass


class Store:
    def __init__(self):
        self.seen: dict[str, dict[str, int]] = {}


store = Store()
other_store = Store()
alias: dict[str, dict[str, int]] = store.seen


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        store.seen["first"] = other
        return isinstance(other, Table)


table = Table({"x": 6})
print(Probe() == table)
print(type(alias["first"]).__name__, alias["first"] is table, alias is store.seen)
alias["first"]["y"] = 7
print(table, store.seen, other_store.seen)
