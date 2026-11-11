# typing.TypeGuard helpers (mypy/types.py is_named_instance)
from typing import TypeGuard
class Type:
    pass
class Instance(Type):
    def __init__(self, name: str) -> None:
        self.name = name
def is_instance(t: Type) -> TypeGuard[Instance]:
    return isinstance(t, Instance)
def f(t: Type) -> str:
    if is_instance(t):
        return t.name
    return "?"
print(f(Instance("int")), f(Type()))
