def snapshot(values: list[int]) -> tuple[int, ...]:
    return tuple(values)

for count in [0, 1, 2, 3, 4, 10]:
    values: list[int] = [i for i in range(count)]
    alias = values
    result = snapshot(values)
    equal = tuple(values)
    changed = tuple([i + 1 for i in range(count)])
    result_alias = result
    if count > 0:
        alias[0] = 999
    alias.append(998)
    values[-1] = 997
    print("snapshot", count, result, result_alias, repr(result), len(result))
    print("attributes", hasattr(result, "__len__"), hasattr(result, "__getitem__"),
          hasattr(result, "__iter__"), hasattr(result, "__setitem__"), hasattr(result, "append"))
    print("equal", result == equal, result != equal, result == tuple(values))
    print("changed", result == changed, result != changed)
    for member in result:
        print("member", member)
    if count > 0:
        print("ends", result[0], result[-1])
    indices: list[int] = [len(result), -len(result) - 1]
    for index in indices:
        try:
            print(result[index])
        except IndexError as error:
            print("bounds", index, str(error))
