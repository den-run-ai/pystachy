# pystachy: dynamic-any
from typing import Any
from mods.constructor_hierarchy import Total, Bonus


def inspect(value: Any) -> None:
    print(isinstance(value, Total), isinstance(value, Bonus))
    print(type(value) is Bonus, value.score())


def typed(value: Total) -> Any:
    return value


base = Total([1, 2])
child = Bonus((3, 4))
inspect(typed(base))
inspect(typed(child))
boxed: Any = child
print(boxed is child)
boxed.bonus = 10
print(child.score())
