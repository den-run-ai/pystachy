# Comparison hints must keep the established argument-only inference. A child
# empty call cannot lock in a layout before another child shows a different one.
def empty(n):
    print("empty", n)
    return []


def values(n):
    print("values", n)
    return [n]


def first(n):
    return [empty(n), [n]]


def last(n):
    return [[n], empty(n)]


def opaque_first(n):
    return [empty(n), values(n)]


def opaque_last(n):
    return [values(n), empty(n)]


expected_first: list[list[str]] | float = [[], ["x"]]
expected_last: list[list[str]] | float = [["x"], []]
print(expected_first == first(1))
print(expected_last == last(1))
print(expected_first == opaque_first(1))
print(expected_last == opaque_last(1))
precise: list[list[float]] | str = [[], [9007199254740992.0]]
print(precise == first(9007199254740993))


def mapping_first(n):
    return {"first": empty(n), "last": [n]}


def mapping_last(n):
    return {"first": [n], "last": empty(n)}


def opaque_mapping_first(n):
    return {"first": empty(n), "last": values(n)}


def opaque_mapping_last(n):
    return {"first": values(n), "last": empty(n)}


map_first: dict[str, list[str]] | float = {"first": [], "last": ["x"]}
map_last: dict[str, list[str]] | float = {"first": ["x"], "last": []}
print(map_first == mapping_first(1))
print(map_last == mapping_last(1))
print(map_first == opaque_mapping_first(1))
print(map_last == opaque_mapping_last(1))


def empty_mapping(n):
    print("empty mapping", n)
    return {}


def table(n):
    print("table", n)
    return {n: n}


def dict_first(n):
    return [empty_mapping(n), {n: n}]


def dict_last(n):
    return [{n: n}, empty_mapping(n)]


def opaque_dict_first(n):
    return [empty_mapping(n), table(n)]


def opaque_dict_last(n):
    return [table(n), empty_mapping(n)]


dicts_first: list[dict[str, str]] | float = [{}, {"x": "x"}]
dicts_last: list[dict[str, str]] | float = [{"x": "x"}, {}]
print(dicts_first == dict_first(1))
print(dicts_last == dict_last(1))
print(dicts_first == opaque_dict_first(1))
print(dicts_last == opaque_dict_last(1))


def tuple_first(n):
    return [(empty(n),), ([n],)]


def tuple_last(n):
    return [([n],), (empty(n),)]


tuples_first: list[tuple[list[str]]] | float = [([],), (["x"],)]
tuples_last: list[tuple[list[str]]] | float = [(["x"],), ([],)]
print(tuples_first == tuple_first(1))
print(tuples_last == tuple_last(1))


def local(n):
    result = [empty(n), [n]]
    alias = result
    return alias


print(expected_first == local(1))


# Search operations also supply comparison hints rather than storage contracts.
haystack: list[list[list[str]] | float] = [[[], ["x"]]]
print(first(1) in haystack, haystack.count(first(1)))
try:
    print(haystack.index(first(1)))
except ValueError:
    print("missing")
try:
    haystack.remove(first(1))
except ValueError:
    print("remove missing")
print(haystack)
print(expected_first == first(1) == expected_first)
