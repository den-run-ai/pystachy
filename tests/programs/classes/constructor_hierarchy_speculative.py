# pystachy: dynamic-any
from typing import Any
from mods.constructor_hierarchy import Total
from mods.constructor_hierarchy_factories import Dormant, Active


def score(value: Total) -> int:
    return value.score()


# Building an Any constructor adapter for the never-called factory may decline.
# It must not activate Invalid or make Total's ordinary dispatch compile it.
dormant: Any = Dormant
active: Any = Active
print(active(4).value)
print(score(Total([3])))
