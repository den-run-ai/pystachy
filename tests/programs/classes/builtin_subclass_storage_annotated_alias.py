# Every alias adopts the original allocation's tagged item layout, including annotated
# aliases outside the path that first stores a subclass.
class Stack(list[int]):
    pass


seen: list[list[int]] = []
alias: list[list[int]] = seen
middle = alias
last: list[list[int]] = middle
sibling: list[list[int]] = seen


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        last.append(other)
        return isinstance(other, Stack)


def inspect(items: list[list[int]]):
    print(type(items[0]).__name__)
    return items


s = Stack([1])
print(Probe() == s)
print(seen is alias, alias is middle, last is sibling)
print(type(seen[0]).__name__, seen[0] is s)
sibling[0].append(2)
print(s, inspect(alias) is seen)
plain = [3]
sibling.append(plain)
print(type(last[1]).__name__, last[1] is plain)


def local_aliases():
    original: list[list[int]] = []
    first: list[list[int]] = original
    second: list[list[int]] = original
    value = Stack([4])
    first.append(value)
    print(first is second, type(second[0]).__name__, second[0] is value)
    second[0].append(5)
    print(value)


local_aliases()
table: dict[str, list[int]] = {}
map_alias: dict[str, list[int]] = table
map_sibling: dict[str, list[int]] = table
map_alias["item"] = s
print(table is map_alias, map_alias is map_sibling)
print(type(table["item"]).__name__, map_sibling["item"] is s)
