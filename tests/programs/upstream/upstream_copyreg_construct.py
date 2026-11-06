# pystachy: dynamic-any
# Unchanged copyreg registration bodies; reducers return actual user classes.
from typing import Any
from registrymods import copyreg_slice as copyreg


class Entry:
    def __init__(self, data: list[Any], label: str) -> None:
        self.data = data
        self.label = label


class SpecialEntry(Entry):
    pass


def reduce_entry(value: Any) -> Any:
    return (type(value), (value.data, value.label))


def restore(value: Any) -> Any:
    reducer = copyreg.dispatch_table[type(value)]
    factory, arguments = reducer(value)
    # Runtime-sized *arguments remains separate; these reductions have two items.
    return factory(arguments[0], arguments[1])


copyreg.pickle(Entry, reduce_entry, Entry)
copyreg.pickle(SpecialEntry, reduce_entry, SpecialEntry)
shared: list[Any] = [7, "state", [1, 2]]
originals: list[Any] = [Entry(shared, "base"), SpecialEntry(shared, "child")]
copies: list[Any] = []
for original in originals:
    copied = restore(original)
    copies.append(copied)
    print(type(copied) is type(original), copied is original)
    print(copied.label, copied.data is original.data, copied.data)

print(type(copies[0]) is Entry, type(copies[1]) is SpecialEntry)
print(copies[0].data is copies[1].data)
copies[0].data.append("shared")
print(originals[0].data, originals[1].data, copies[1].data)
print(copyreg.dispatch_table[Entry] is reduce_entry)
print(copyreg.dispatch_table[SpecialEntry] is reduce_entry)
