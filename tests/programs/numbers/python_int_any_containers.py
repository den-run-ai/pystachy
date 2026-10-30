# pystachy: dynamic-any
# Dynamic storage already holds boxes and must preserve wide values and aliases.
from typing import Any
from any_wide_values import make

value = make(70)
other = make(70)
items: list[Any] = [value, value, other, -value, 7, "end"]
print(items)
print(items[0] is items[1], items[0] is items[2], items[0] == items[2])
copy = items[:]
copy.append(value)
print(copy[0] is items[0], copy[-1] is items[0])
items[0] = -value
print(copy, items)
numbers: list[Any] = [value + 1, -value, value, 7, float(value), 0]
print(sorted(numbers))
print(min(numbers), max(numbers), value in numbers, value - 1 in numbers)
print(numbers.count(value), numbers.index(value), sum(numbers[:4]))
pair: tuple[Any, ...] = (value, -value, value)
print(pair, pair[0] is pair[2], list(pair))
entries: dict[Any, Any] = {value: "wide", float(value): "float", 1: "one", True: "bool"}
print(len(entries), entries[value], entries[float(value)], entries[1], entries[True])
print(list(entries.keys()), list(entries.values()))
entries[-value] = value
entries[value + 1] = -value
print(entries[-value], entries[value + 1], value in entries, value + 2 in entries)
print(entries.get(value), entries.get(value + 2, "missing"))
print(entries.pop(value + 1), len(entries))
for key in entries:
    print(key, type(key).__name__)
copied = entries.copy()
print(copied == entries, copied[-value] is entries[-value])
del entries[-value]
print(len(entries), copied[-value])
