# Container elements compare by identity before recursing. NaN makes the missing
# shortcut observable without making an unfixed runtime traverse an enormous DAG.
calls = 0
orders = 0


class Probe:
    def __init__(self, value: int):
        self.value = value

    def __eq__(self, other: "Probe") -> bool:
        global calls
        calls += 1
        return self.value == other.value

    def __lt__(self, other: "Probe") -> bool:
        global orders
        orders += 1
        return self.value < other.value


leaf = [float("nan")]
mapping = {0: float("nan")}
pair = (float("nan"),)
print("list", [leaf] == [leaf], [mapping] == [mapping], [pair] == [pair])
print("dict", {0: leaf} == {0: leaf}, {0: mapping} == {0: mapping}, {0: pair} == {0: pair})
print("tuple", (leaf,) == (leaf,), (mapping,) == (mapping,), (pair,) == (pair,))
print("order", [leaf] < [leaf], [leaf] <= [leaf], (leaf,) > (leaf,), (leaf,) >= (leaf,))

# The common child is skipped, so the following distinct objects are compared.
left = (leaf, Probe(1))
right = (leaf, Probe(2))
print("callbacks", left == right, calls, left < right, calls, orders)
print("objects", [left[1]] == [left[1]], calls)

haystack = [leaf, leaf]
print("search", leaf in haystack, haystack.index(leaf), haystack.count(leaf))
haystack.remove(leaf)
print("remove", len(haystack), haystack[0] is leaf)
print("other kinds", mapping in [mapping], [mapping].count(mapping), pair in [pair], [pair].index(pair))
print("distinct", [float("nan")] in [leaf], {0: float("nan")} in [mapping], (float("nan"),) in [pair])


def optional_list(value: list[float] | None) -> None:
    values = [value, None, value]
    print("optional list", values == [value, None, value], value in values, values.index(value), values.count(value))


def optional_dict(value: dict[int, float] | None) -> None:
    values = [value, None, value]
    print("optional dict", values == [value, None, value], value in values, values.index(value), values.count(value))


def optional_tuple(value: tuple[float] | None) -> None:
    values = [value, None, value]
    print("optional tuple", values == [value, None, value], value in values, values.index(value), values.count(value))


optional_list(leaf)
optional_list(None)
optional_dict(mapping)
optional_dict(None)
optional_tuple(pair)
optional_tuple(None)

# Sharing at several levels, with only a few live lists. The deterministic C
# probe tests deep sharing and fails an unfixed runtime before traversal grows.
a = [1]
b = [a] * 4
c = [b] * 4
d = [c] * 4
print("dag", [d, d] == [d, d], d in [d], [d].count(d))
