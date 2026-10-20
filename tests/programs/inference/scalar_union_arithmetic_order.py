"""Operand order, snapshots, mutation and lifetime under GC stress."""

def describe(value: int | float) -> str:
    if isinstance(value, int):
        return "int:" + str(value)
    return "float:" + str(value)

trace: list[str] = []

def operand(label: str, value: int | float | bool | None, fail: bool) -> int | float | bool | None:
    trace.append(label)
    if fail:
        raise ValueError(label)
    for i in range(20):
        junk = str(i) * 50
        if len(junk) == 0:
            raise AssertionError("empty")
    return value

def evaluate(a: int | float | bool | None, b: int | float | bool | None, fail_left: bool, fail_right: bool) -> str:
    try:
        return describe(operand("left", a, fail_left) + operand("right", b, fail_right))
    except TypeError as error:
        return str(error)
    except ValueError as error:
        return str(error)

print(evaluate(3, 0.5, False, False), trace)
trace.clear()
print(evaluate(None, 3, False, False), trace)
trace.clear()
print(evaluate(None, 3, False, True), trace)
trace.clear()
print(evaluate(None, 3, True, False), trace)
trace.clear()

class Counter:
    def __init__(self, value: int | float):
        self.value = value

    def change(self) -> int | float:
        self.value = 2.5
        return self.value

counter = Counter(10)
print(describe(counter.value + counter.change()), describe(counter.value))
counter.value += 1
print(describe(counter.value))

def repeat(value: int | float) -> int | float:
    result: int | float = value
    for i in range(100):
        result = result + 1
    return result

print(describe(repeat(5)), describe(repeat(0.5)))

def always_raises(value: int | float) -> int | float:
    return value + None

try:
    always_raises(1)
except TypeError as error:
    print(str(error))

def scalar_return_raises(value: int | float) -> int:
    return value + None

def assignment_raises(value: int | float) -> int:
    result: int = value + None
    return result

try:
    scalar_return_raises(1.5)
except TypeError as error:
    print(str(error))
try:
    assignment_raises(1)
except TypeError as error:
    print(str(error))

def negative(value: int | float | None) -> int | float:
    return -value

try:
    negative(None)
except TypeError as error:
    print(str(error))
