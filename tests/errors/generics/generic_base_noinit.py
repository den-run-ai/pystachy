# error: generic_base_noinit.py:8: error: a generic class with a base needs an __init__ of its own, whose arguments bind its type variables, as its generic base does (Fut)
# (A generic class without a base or an __init__ binds nothing: generic_without_init.py.)
from typing import Generic, TypeVar
T = TypeVar("T")
class Base:
    def __init__(self) -> None:
        self.n = 0
class Fut(Base, Generic[T]):
    def get(self) -> int:
        return self.n
print(Fut().get())
