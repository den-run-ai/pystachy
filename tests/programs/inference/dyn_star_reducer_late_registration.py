# pystachy: dynamic-any
# Required method dispatch can register a class after the first packed call.
from typing import Any
from registrymods.runtime_late_calls import Holder


def good() -> int:
    return 7


def other(left, right):
    return left + right


held: Any = Holder()
functions: list[Any] = [good, other]
empty: Any = []
print(functions[0](*empty))
print(held.get() is None)


class Empty:
    pass


original: Any = Empty()
factory: Any = type(original)
args: Any = [1]
keywords: Any = {"x": 2}
bad_keys: Any = {1: 2}
print(type(factory(*empty)) is Empty)
try:
    factory(*args)
except TypeError as error:
    print("positional", str(error))
try:
    factory(**keywords)
except TypeError as error:
    print("keyword", str(error))
try:
    factory(**bad_keys)
except TypeError as error:
    print("nonstring", str(error))
