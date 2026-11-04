# pystachy: dynamic-any
# Different physical list descriptors still have exactly the builtin list type.
from typing import Any


def inspect(value: Any) -> None:
    print("named", type(value) is list, type(value) == list,
          list is type(value), list == type(value),
          type(value) is not list, type(value) != list)
    print("class", value.__class__ is list, isinstance(value, list),
          isinstance(value, (list, dict)), type(value).__name__)


def compare(value: Any, native: list[int], floats: list[float], boxed: list[Any]) -> None:
    print("other layouts", type(value) is type(native), type(native) == type(value),
          type(value) == type(floats), type(floats) is type(value),
          type(value) is type(boxed), type(boxed) == type(value))


class Base:
    pass


class Child(Base):
    pass


native: list[int] = [1, 2]
floats: list[float] = [1.0]
boxed: list[Any] = [1, "two"]
for value in [native, boxed, "text", None]:
    inspect(value)
    compare(value, native, floats, boxed)
child: Any = Child()
print("class distinction", type(child) is Base, type(child) is Child,
      type(child) is list, isinstance(child, Base))
