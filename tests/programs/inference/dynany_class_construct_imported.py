# pystachy: dynamic-any
# A normal call compiles an imported initializer for later stored-class calls.
from typing import Any
from registrymods.construct_imported import ImportedRecord


shared: list[Any] = [1, "shared"]
original: Any = ImportedRecord(shared, "original")
factory: Any = type(original)
first = factory(shared)
second = factory(label="keyword", data=shared)
print(factory is ImportedRecord, type(first) is ImportedRecord, type(second) is ImportedRecord)
print(first is original, second is original, first is second)
print(first.label, second.label, original.label)
print(first.data is shared, second.data is shared)
first.data.append(3)
print(original.data, second.data)
