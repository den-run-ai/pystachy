def maybe(present: bool) -> tuple[int, ...] | None:
    return tuple([1, 2]) if present else None


def optional_list(present: bool) -> list[int] | None:
    return [1, 2] if present else None


for present in [False, True]:
    values = maybe(present)
    print("optional-tuple", values, bool(values), isinstance(values, tuple))
    print("literal-equality", values == (1, 2), (1, 2) == values, values != (1, 2))
    try:
        print("length", len(values))
    except TypeError as error:
        print("length-error", str(error))
    try:
        print("item", values[0])
    except TypeError as error:
        print("item-error", str(error))
    try:
        for value in values:
            print("iteration", value)
    except TypeError as error:
        print("iteration-error", str(error))
    try:
        print("construct", tuple(optional_list(present)))
    except TypeError as error:
        print("construct-error", str(error))

integers: list[int | None] = [1, None, -1]
floats: list[float | None] = [0.5, None, -1.5]
booleans: list[bool | None] = [True, None, False]
print("integers", tuple(integers), list(tuple(integers)))
print("floats", tuple(floats), list(tuple(floats)))
print("booleans", tuple(booleans), list(tuple(booleans)))
