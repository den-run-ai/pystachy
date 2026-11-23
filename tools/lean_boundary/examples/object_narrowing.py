# isinstance(x, int) narrows a value of object to int | bool: the caller tests for a bool, asks
# the bool or the int entry of the object's table and makes the union itself, so each of the
# union's tag and payload reads below (x + 1, the comparison, str()) has its member proved
# (GUARDS.md, test_lean_guard_object.py)
def bump(x: object) -> int:
    if isinstance(x, int):
        return x + 1
    return 0


def describe(x: object) -> str:
    if isinstance(x, int) and x > 1:
        return "int " + str(x)
    return "other"


values: list[object] = [1, True, "a", 7, None]
print([bump(v) for v in values], [describe(v) for v in values])
