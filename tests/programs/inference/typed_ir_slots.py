"""Native values survive container slots without losing their representation."""


class Box:
    def __init__(self, value: int):
        self.value = value


# User class names share the spelling of runtime signature variables.
class T:
    def __init__(self, value: int):
        self.value = value


print([T(13)][0].value)


def describe(value: int | float | bool | str | None) -> str:
    if isinstance(value, bool):
        return "bool:" + str(value)
    if isinstance(value, int):
        return "int:" + str(value)
    if isinstance(value, float):
        return "float:" + str(value)
    if isinstance(value, str):
        return "str:" + value
    return "none"


floats = [0.0, -0.0, 1.25, float("inf"), float("-inf"), float("nan")]
for value in floats:
    # Equality is deterministic for NaN and retains the sign of zero in str().
    print(str(value), value == value)
booleans = [False, True, False]
print(booleans[0], booleans[1], booleans[2])
strings = ["", "value", "retained"]
print(strings[0], strings[1], strings[2])
missing: list[str | None] = [None, "present"]
print(missing[0], missing[1])
objects = [Box(7), Box(9)]
retained = objects[0]
objects[0] = Box(11)
print(retained.value, objects[0].value, objects[1].value)
nested = [[1.5, -0.0], [2.5]]
print(nested[0][0], nested[0][1], nested[1][0])
mapping = {"first": 1.25, "second": -0.0}
print(mapping["first"], mapping["second"])
pair = (True, -0.0, "tuple", None)
print(pair[0], pair[1], pair[2], pair[3])
optional: list[float | None] = [None, -0.0, 2.5]
for maybe in optional:
    print(maybe)
mixed: list[int | float | bool | str | None] = [4, -0.0, True, "union", None]
for item in mixed:
    print(describe(item))
