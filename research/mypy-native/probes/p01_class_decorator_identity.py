# mypy: @trait / @mypyc_attr(...) / @final are identity class decorators (mypy/nodes.py:245, mypy/visitor.py)
from typing import Callable, TypeVar
T = TypeVar("T")
def trait(cls: T) -> T:
    return cls
def mypyc_attr(*attrs: str, **kw: object) -> Callable[[T], T]:
    return lambda x: x
@trait
class A:
    def f(self) -> int:
        return 1
@mypyc_attr(allow_interpreted_subclasses=True)
class B(A):
    def f(self) -> int:
        return 2
print(A().f(), B().f())
