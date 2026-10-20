# error: type_alias_value_single_starred.py:6: error: typing.Optional requires a single type (CPython evaluates this type alias's value when the assignment runs)
# (a starred argument is never a single type: CPython raises the TypeError there)
from typing import ClassVar, Optional

Maybe = Optional[int]
Wrong = Optional[*tuple[int, str]]
print("never")
