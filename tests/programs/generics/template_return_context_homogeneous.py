# Caller annotations choose a fresh result's storage before it is allocated.
def values(item):
    return [item, item]


def mapping(key, item):
    return {key: item}


def nested(item):
    return ([item], {"value": [item]})


narrow: list[int | float] = values(9007199254740993)
wide: list[int | float | str] = values(9007199254740993)
optional: list[int | None] = values(9007199254740993)
wide.append("wide")
optional.append(None)
print(narrow, wide, optional)
print(isinstance(narrow[0], int), narrow[0] == 9007199254740993)
print(values(1))  # no context keeps the usual homogeneous specialization

by_key: dict[tuple[str, int], int | float] = mapping(("key", 1), 9007199254740993)
by_key["key", 2] = 2.5
print(by_key, isinstance(by_key["key", 1], int))
wrapped: tuple[list[int | str], dict[str, list[int | None]]] = nested(7)
wrapped[0].append("nested")
wrapped[1]["value"].append(None)
print(wrapped)


# Each return branch constructs the same explicitly selected representation.
def branches(flag, integer, decimal):
    if flag:
        return [integer]
    return [decimal]


def dict_branches(flag, integer, decimal):
    if flag:
        return {"item": integer}
    return {"item": decimal}


def tuple_branches(flag, integer, decimal):
    if flag:
        return ([integer],)
    return ([decimal],)


def scalar_tuple_branches(flag, integer, decimal):
    if flag:
        return (integer,)
    return (decimal,)


for selected in [True, False]:
    result: list[int | float] = branches(selected, 9007199254740993, 2.5)
    entries: dict[str, int | float] = dict_branches(selected, 9007199254740993, 2.5)
    record: tuple[list[int | float]] = tuple_branches(selected, 9007199254740993, 2.5)
    scalar_record: tuple[int | float] = scalar_tuple_branches(selected, 9007199254740993, 2.5)
    result.append(4.5)
    print(result, entries, record, scalar_record, isinstance(result[0], int))


def maybe(flag, item):
    if flag:
        return None
    return [item]


absent: list[int | str] | None = maybe(True, 7)
present: list[int | str] | None = maybe(False, 7)
print(absent, present)


def optional_set(item):
    return {(item,)}


members: set[tuple[str | None]] = optional_set("item")
members.add((None,))
print(len(members), ("item",) in members, (None,) in members)


# Existing comparison hints must not force a fresh result into an incompatible
# representation, or turn an integer into a float before exact equality.
def compared(item):
    return [values(item)]


numbers: list[float] | str = [9007199254740992.0]
words: list[str] | int = ["x"]
number_pairs: list[list[float]] | str = [[9007199254740992.0, 9007199254740992.0]]
print(numbers == values(9007199254740993), words == values(1))
print(number_pairs == compared(9007199254740993))
print([1, 1] in compared(1))
