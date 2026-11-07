# error: type() of a Callable value is not supported: its Python callable identity was erased
# pystachy: dynamic-any
from typing import Callable

typed: Callable[[str], int] = int
cls = type(typed)
print(cls.__name__)
