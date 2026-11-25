# A helper's stores request tagged slots at the caller's fresh allocation. Calls
# preserve both outer-container aliases and each stored object's original identity.
class Stack(list[int]):
    pass


seen: list[list[int]] = []
other_seen: list[list[int]] = []
made = 0


def store(where: list[list[int]], value):
    where.append(value)
    return where


def forward(where: list[list[int]], value):
    alias: list[list[int]] = where
    return store(alias, value)


def make_value():
    global made
    made += 1
    return Stack([made])


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        result = forward(seen, other)
        print(result is seen, result[0] is other)
        return isinstance(other, Stack)


s = Stack([7])
print(Probe() == s)
print(type(seen[0]).__name__, seen[0] is s)
print(forward(other_seen, s) is other_seen)
print(other_seen is seen, other_seen[0] is seen[0])
print(store(value=make_value(), where=seen) is seen, made)
print(type(seen[1]).__name__, seen[1])
seen[0].append(8)
print(other_seen[0], s)


def map_store(where: dict[str, list[int]], key: str, value):
    where[key] = value
    return where


mapping: dict[str, list[int]] = {}
map_alias: dict[str, list[int]] = mapping
print(map_store(map_alias, "s", s) is mapping)
print(type(mapping["s"]).__name__, mapping["s"] is s)
