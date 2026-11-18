# pystachy: dynamic-any
# type[object] in a module that opts in to dynamic Any: an Any value holds the same class
# value, and a display of unrelated classes keeps its Any values.
from typing import Any


class A:
    pass


class C:
    pass


def describe(k: type[object]) -> str:
    return k.__name__


boxes = [A, C]
anyk: Any = C
typed: type = A
typed2: type[object] = anyk
print(boxes, anyk, typed, typed2, describe(A), describe(typed2), typed2 is C)
mixed: list[Any] = [typed, 5, "x"]
print(mixed, mixed[0] is A, isinstance(A(), typed), isinstance(C(), typed))
reg: dict[type, str] = {A: "a", C: "c"}
print(reg[typed2], reg.get(type(A())), len(reg))
