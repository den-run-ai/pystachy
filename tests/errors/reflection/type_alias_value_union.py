# error: type_alias_value_union.py:4: error: Cannot take a Union of no types (CPython evaluates this type alias's value when the assignment runs)
from typing import Union

Nothing = list[int] | Union[()]
