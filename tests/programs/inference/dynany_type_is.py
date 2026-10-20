# pystachy: dynamic-any
# type(x) is C, type(x) == C and type(x) is type(y) of Any values compare their exact types, as
# CPython's do: a bool is no int and a subclass's object no object of its base there (#782);
# type(x).__qualname__ and __module__ name a class.
from typing import Any


class Base:
    pass


class Sub(Base):
    pass


vals: list[Any] = [1, 2.5, "s", True, None, [1], {"k": 1}, (1,), Base(), Sub()]
for v in vals:
    print(type(v).__name__, type(v) is int, type(v) == float, type(v) is bool, type(v) is str, type(v) is list,
          type(v) is dict, type(v) is tuple, type(v) is type(None), type(v) is Base, type(v) is not Sub, type(v) is set)
a: Any = 1
b: Any = 2
c: Any = "x"
d: Any = Sub()
e = Sub()
print(type(a) is type(b), type(a) == type(c), type(d) is type(e), type(e) is type(d), type(d) is type(Base()))
print(type(d).__qualname__, type(a).__qualname__, type(d).__module__, type(c).__module__)
