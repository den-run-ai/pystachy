# error: type_alias_value_classvar_starred.py:3: error: typing.ClassVar accepts only single type (CPython evaluates this type alias's value when the assignment runs)
from typing import ClassVar
Counter = ClassVar[*tuple[int]]
