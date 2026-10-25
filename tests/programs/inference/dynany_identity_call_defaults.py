# pystachy: dynamic-any
# A numeric default is one definition-time object, also in an escaped closure.
from typing import Any, Callable


N = int("1000")
F = float("nan")


def int_default(value: int = N) -> Any:
    return value


def float_default(value: float = F) -> Any:
    return value


def literal_default(value: int = 1000) -> Any:
    return value


def make_default(value: Any) -> Callable[[], Any]:
    typed: float = value

    def read(item: float = typed) -> Any:
        return item

    return read


def churn() -> None:
    for i in range(30):
        str(i) + str(i + 1)


old: Any = N
old_float: Any = F
N = int("1000")
F = float("nan")
a = int_default()
b = int_default()
print("definition int", a is old, a is b, a is N, id(a) == id(old))
c = float_default()
d = float_default()
print("definition float", c is old_float, c is d, c is F)
literal: Any = 1000
print("literal default", literal_default() is literal_default(), literal_default() is literal)
items: set[Any] = {old_float, float_default(), float_default()}
print("default nan keys", len(items))
value: Any = float("nan")
read = make_default(value)
churn()
e = read()
f = read()
print("closure default", value is e, e is f, id(value) == id(e))
other = make_default(float("nan"))
print("separate definitions", read() is other())
