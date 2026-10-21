# error: generic_ann_unbound.py:13: error: Box() does not bind its type variable 'T': no argument's type gives it; name it where the object goes (q: Box[int] = Box(...), a field or a parameter annotated so) or in the call (Box[int](...))
# a generic class's object with no annotation where it goes, and no argument that binds T
from typing import Generic, Iterable, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, items: Iterable[T] = ()) -> None:
        self.items: list[T] = list(items)


b = Box()
print(b.items)
