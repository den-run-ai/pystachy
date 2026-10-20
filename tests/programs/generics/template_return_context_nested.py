# Distinct result contexts for the same arguments require distinct layouts,
# including tuple-key dict metadata and scalar boxes inside fresh displays.
def nested(key):
    return ([], {key: []}, {(): {}})


def forward(key):
    return nested(key)


strings: tuple[list[str], dict[str, list[int]], dict[tuple[()], dict[str, int]]] = nested("key")
numbers: tuple[list[int], dict[str, list[str]], dict[tuple[()], dict[int, str]]] = nested("key")
wrapped: tuple[list[float], dict[str, list[int]], dict[tuple[()], dict[tuple[str, int], str]]] = forward("key")
strings[0].append("a")
strings[1]["key"].append(1)
strings[2][()]["word"] = 2
numbers[0].append(3)
numbers[1]["key"].append("b")
numbers[2][()][4] = "c"
wrapped[0].append(1.5)
wrapped[2][()]["tuple", 5] = "value"
print(strings, numbers, wrapped)
print(strings[2][()]["word"], numbers[2][()][4], wrapped[2][()]["tuple", 5])


def mixed(a, b):
    return ([a, b], 9007199254740993, [])


result: tuple[list[int | str], int, list[float]] = mixed(1, "x")
result[2].append(2.5)
print(result, isinstance(result[1], int))


def final(a, b):
    try:
        return ([a, b], {})
    finally:
        print("finally")


finished: tuple[list[int | str], dict[tuple[str, int], str]] = final(1, "x")
finished[1]["key", 2] = "value"
print(finished)


# Membership passes its element type as an expression hint for the container.
# Forwarded empty results must remain open when that hint has another shape.
def empty(n):
    return []


def items(flag):
    if flag:
        return empty(1)
    return [([1],)]


print(([1],) in items(True), ([1],) in items(False))
