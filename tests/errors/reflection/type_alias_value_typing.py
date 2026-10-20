# error: type_alias_value_typing.py:5: error: Too many arguments for typing.Iterable; actual 2, expected 1 (CPython evaluates this type alias's value when the assignment runs)
from typing import Iterable, Union

Fine = Union[int, str]
Index = dict[str, Iterable[int, str]]
print("never")
