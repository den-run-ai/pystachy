# pystachy: dynamic-any
# pystachy: python-int
# Promoting typed storage and dynamic numeric identity must coexist without copies.
from bisect import bisect_left
from heapq import heappop, heappush
from typing import Any


def same(a: Any, b: Any) -> bool:
    return a is b and id(a) == id(b)


def change(values: list[int], value: int) -> None:
    values.append(value)


value = 2 ** 70
independent = int("1180591620717411303424")
minimum = -2 ** 63
negative = -value
higher = value + 1
values: list[int] = [value, value, minimum, negative, 3]
alias = values
print(values, same(values[0], value), same(values[0], values[1]))
copy = values[:]
print(same(copy[0], value), copy is values, copy == values)
values[0] = independent
print(same(values[0], value), same(values[1], value), same(copy[0], value))
change(values, higher)
print(alias, alias is values)
values.reverse()
values.sort()
print(values, sum(values), min(values), max(values), bisect_left(values, value))
print(same(values[3], value), same(values[4], independent), same(values[4], value))
print(same(min(values), negative), same(max(values), higher))
selected: list[int] = [value, independent, value]
print(same(min(selected), value), same(max(selected), value), same(selected.pop(1), independent))
heappush(values, -2 ** 80)
print(heappop(values), values, alias is values)
copies = copy * 2
print(copies, same(copies[0], copies[5]), same(copies[1], value))
mapping: dict[int, int] = {value: -value, minimum: value, 1: minimum}
mapping_alias = mapping
mapping[value + 1] = value + 2
print(mapping, mapping[value], mapping.get(value + 1), mapping_alias is mapping)
print(list(mapping.keys()), list(mapping.values()), list(mapping.items()))
mapping_copy = mapping.copy()
print(mapping_copy == mapping, mapping_copy.pop(value), mapping[value])
elements: set[int] = {value, -value, minimum, 1}
elements.add(value + 1)
print(sorted(elements), value in elements, value + 2 in elements)
elements.remove(value)
print(sorted(elements), sorted(elements | {value}), sorted(elements & {minimum, 1}))
boxed: list[Any] = [copy[0], mapping[minimum], value]
print(boxed, same(boxed[0], boxed[2]), boxed[1] == boxed[2])
