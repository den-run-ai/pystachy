# pystachy: dynamic-any
# hasattr(x, "name") of an Any value: a builtin type's attributes as CPython 3.13's, an object's
# fields (also one __init__ may leave unassigned), methods and properties as its class's (a getter
# that raises AttributeError is False, another error propagates).
from typing import Any


class Base:
    def __init__(self, full: bool) -> None:
        self.always = 1
        if full:
            self.sometimes = 2

    def method(self) -> int:
        return 3

    @property
    def ready(self) -> int:
        raise AttributeError("not ready")

    @property
    def broken(self) -> int:
        raise ValueError("broken getter")


class Derived(Base):
    def extra(self) -> int:
        return 4


def arg(value: Any) -> Any:
    print("argument", type(value).__name__)
    return value


for value in [[1], "s", 7, True, 2.5, {"k": 1}, (1,), None]:
    print(type(value).__name__, hasattr(value, "append"), hasattr(value, "upper"), hasattr(value, "real"), hasattr(value, "keys"),
          hasattr(value, "count"), hasattr(value, "bit_length"), hasattr(value, "is_integer"), hasattr(value, "__bool__"),
          hasattr(value, "__len__"), hasattr(value, "missing"))

for obj in [Base(True), Base(False), Derived(False)]:
    o: Any = obj
    print(hasattr(o, "always"), hasattr(o, "sometimes"), hasattr(o, "method"), hasattr(o, "extra"), hasattr(o, "ready"), hasattr(o, "missing"), hasattr(o, "__dict__"))
    try:
        print(hasattr(o, "broken"))
    except ValueError as error:
        print("ValueError", error)

print(hasattr(arg([1]), "pop"), hasattr(arg(Base(True)), "sometimes"))
