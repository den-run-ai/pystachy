# A module global annotated Any, given an int and then a str: int | str.
from typing import Any

value: Any = 1
print(repr(value))
value = "text"
print(repr(value))
