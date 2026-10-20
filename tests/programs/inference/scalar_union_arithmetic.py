"""Explicit numeric unions keep Python's result types and native errors."""

def describe(value: int | float) -> str:
    if isinstance(value, int):
        return "int:" + str(value)
    return "float:" + str(value)

def calculate(op: str, a: int | float | bool | None, b: int | float | bool | None) -> int | float:
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        return a / b
    if op == "//":
        return a // b
    return a % b

def unary(value: int | float | bool | None) -> str:
    try:
        return describe(+value) + "," + describe(-value)
    except TypeError as error:
        return str(error)

values: list[int | float | bool | None] = [7, -2, 0, 3.5, -0.0, True, False, None]
for op in ["+", "-", "*", "/", "//", "%"]:
    print(op)
    for a in values:
        for b in values:
            try:
                print(describe(calculate(op, a, b)))
            except TypeError as error:
                print("type", str(error))
            except ZeroDivisionError:
                print("zero")
for value in values:
    print(unary(value))

def exact(value: int | float) -> int | float:
    return value + 1

def quotient(value: int | bool) -> float:
    return value / 2

def optional_operand(value: int | float, other: int | None) -> int | float:
    return other + value

print(describe(exact(9007199254740992)), describe(exact(2.5)))
print(quotient(3), quotient(True))
print(describe(optional_operand(1.5, 2)))
try:
    print(describe(optional_operand(1.5, None)))
except TypeError as error:
    print(str(error))
