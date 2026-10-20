"""Each union operand is compared through its own native storage descriptor."""

values: list[int | str | list[int] | list[float] | list[str] | list[list[int]] | dict[str, int] | dict[str, float] | dict[int, int] | None] = [
    1, "1", [1], [1.0], ["1"], [[1]], {"x": 1}, {"x": 1.0}, {1: 1}, None,
]
for a in values:
    bits = ""
    for b in values:
        bits += "1" if a == b else "0"
        assert (a != b) == (not (a == b))
    print(bits)

def nested(a: list[int | str | None] | list[float | bool | None],
           b: list[int | str | None] | list[float | bool | None]) -> bool:
    return a == b

left: list[int | str | None] = [1, 0, None]
right: list[float | bool | None] = [1.0, False, None]
print(nested(left, right))
right[1] = True
print(nested(left, right))

def optional(a: list[int] | list[int | None], b: list[int] | list[int | None]) -> bool:
    return a == b

plain = [1, 2]
boxed: list[int | None] = [1, 2]
print(optional(plain, boxed))
boxed[0] = None
print(optional(plain, boxed))

def exact(a: list[int] | list[float], b: list[int] | list[float]) -> bool:
    return a == b

print(exact([9007199254740993], [9007199254740992.0]))
print(exact([9223372036854775807], [9223372036854775808.0]))
print(exact([-9007199254740992], [-9007199254740992.0]))

def dictionaries(a: dict[tuple[int, str], int] | dict[tuple[bool, str | None], float],
                 b: dict[tuple[int, str], int] | dict[tuple[bool, str | None], float]) -> bool:
    return a == b

dk1: dict[tuple[int, str], int] = {(1, "one"): 1, (0, "zero"): 0}
dk2: dict[tuple[bool, str | None], float] = {(False, "zero"): 0.0, (True, "one"): 1.0}
print(dictionaries(dk1, dk2), dictionaries(dk2, dk1))
dk2[(True, None)] = 2.0
print(dictionaries(dk1, dk2))

def tuples(a: list[tuple[int, str]] | list[tuple[float, str]],
           b: list[tuple[int, str]] | list[tuple[float, str]]) -> bool:
    return a == b

print(tuples([(1, "x")], [(1.0, "x")]), tuples([(1, "x")], [(1.0, "y")]))

def counted(a: list[tuple[int, ...]] | list[tuple[float, float]],
            b: list[tuple[int, ...]] | list[tuple[float, float]]) -> bool:
    return a == b

variable: list[tuple[int, ...]] = [(1, 2)]
print(counted(variable, [(1.0, 2.0)]), counted(variable, [(1.0, 3.0)]))
variable[0] = (1,)
print(counted(variable, [(1.0, 2.0)]))

empty_int: dict[int, int] = {}
empty_str: dict[str, float] = {}
def empty(a: dict[int, int] | dict[str, float], b: dict[int, int] | dict[str, float]) -> bool:
    return a == b

print(empty(empty_int, empty_str))
