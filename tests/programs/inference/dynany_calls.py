# pystachy: dynamic-any
# Function values as Any values: defs, defaults, closures, bound methods, objects with
# __call__, typed Callables of Any, and CPython's TypeErrors for a wrong count or a value that
# cannot be called.
from typing import Any, Callable


def add(a: Any, b: Any) -> Any:
    return a + b


def neg(a: Any) -> Any:
    return -a


def greet(name: Any, greeting: Any = "hello") -> Any:
    return greeting + " " + name


def make_scaler(k: int) -> Any:
    def scale(x: Any) -> Any:
        return x * k
    return scale


class Acc:
    def __init__(self) -> None:
        self.total: Any = 0

    def push(self, v: Any) -> Any:
        self.total = self.total + v
        return self.total

    def __call__(self, v: Any) -> Any:
        return self.push(v)


ops: dict[str, Any] = {"add": add, "neg": neg, "greet": greet}
print(ops["add"](2, 3), ops["add"]("a", "b"), ops["neg"](4), ops["neg"](2.5))
print(ops["greet"]("bob"), ops["greet"]("ann", "hi"))
f: Any = make_scaler(3)
print(f(2), f("ab"))
acc = Acc()
m: Any = acc.push
print(m(1), m(2.5), acc.total)
c: Any = acc
print(c(10), acc.total)
handlers: list[Any] = [neg, make_scaler(2), acc]
for h in handlers:
    print(h(5))
typed: Callable[[Any], Any] = neg
print(typed(7))
table: dict[str, Callable[[Any, Any], Any]] = {"add": add}
print(table["add"](1, 1.5))
print(ops["add"] == ops["add"], ops["add"] == ops["neg"], ops["add"] is add)
try:
    ops["neg"](1, 2)
except TypeError as e:
    print("TypeError", e)
try:
    x: Any = 5
    x(1)
except TypeError as e:
    print("TypeError", e)
