"""Explicit scalar unions reuse ordinary truth, formatting and equality operations."""

def inspect(value: int | float | bool | str | None) -> None:
    print(bool(value), not value, str(value), repr(value), f"{value}", f"{value!r}")
    if value:
        print("true")
    else:
        print("false")

values: list[int | float | bool | str | None] = [
    None, False, True, 0, -7, 0.0, -0.0, 2.5, "", "hello", "a'\n\"\\é",
]
for value in values:
    inspect(value)
print(values)
print({"empty": None, "number": values[4], "text": values[9]})
print((values[0], values[4], values[9]))
print(any(values), all(values))

def equal(a: int | float | bool | str | None, b: int | float | bool | str | None) -> None:
    print(a == b, a != b)

numbers: list[int | float | bool | str | None] = [
    None, False, True, 0, 1, 1.0, "1", "", 9007199254740993, 9007199254740992.0,
    9223372036854775807, 9223372036854775808.0, float("inf"), float("nan"),
]
for a in numbers:
    for b in numbers:
        equal(a, b)

def concrete(a: int | str, b: float | str) -> None:
    print(a == 1.0, a != True, a == None, a != None, a == b, b == "1")

concrete(1, 1.0)
concrete("1", "1")

def optional(a: int | str | None, b: int | None) -> None:
    print(a == b, a != b)

optional(None, None)
optional(3, 3)
optional("3", 3)

def choose(a: int | str | None, b: int | str | None) -> None:
    print(a or b, a and b)

choose("", 7)
choose(None, "next")
choose(4, None)
