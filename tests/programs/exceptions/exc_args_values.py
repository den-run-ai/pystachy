# pystachy: dynamic-any
from typing import Any
import sys


e = ValueError()
print(e.args, len(e.args), e.args is e.args, str(e), repr(e))
print(e.args is RuntimeError().args)
e = ValueError("")
print(e.args, str(e), repr(e))
e = ValueError(3, "message", None, True)
print(e.args, e.args[0], e.args[-1], e.args[1:3], str(e), repr(e))

number = int("1000")
original: Any = number
e = ValueError(number)
print(e.args[0] is original, e.args is e.args, e.args)
try:
    raise e
except Exception as caught:
    print(caught is e, caught.args is e.args, caught.args[0] is original)


def rebind() -> str:
    global number
    number = int("2000")
    return "changed"


e = ValueError(number, rebind())
print(e.args[0] is original, number, e.args)
number = int("1000")
original = number

items: list[Any] = [1, "two"]
e = RuntimeError(items)
print(e.args[0] is items)
items.append(3)
print(e.args[0])

stop = StopIteration(number, "extra")
print(stop.args, stop.value, stop.value is original)
print(StopIteration().value is None, StopIteration(None).args)
print(KeyError("key").args, OSError(2, "missing", "path").args)
print(SystemExit().args, SystemExit(None).args, SystemExit(False).args)
try:
    sys.exit(None)
except SystemExit as ended:
    print(ended.args)
try:
    sys.exit(number)
except SystemExit as ended:
    print(ended.args, ended.args[0] is original)

try:
    print([1][3])
except IndexError as error:
    print(error.args, error.args is error.args)
try:
    print(int("bad"))
except ValueError as error:
    print(error.args, error.args is error.args)

try:
    assert False
except AssertionError as error:
    print(error.args)
try:
    assert False, ""
except AssertionError as error:
    print(error.args)
try:
    assert False, number
except AssertionError as error:
    print(error.args, error.args[0] is original)
try:
    print(ValueError("x").value)
except AttributeError as error:
    print(str(error))
