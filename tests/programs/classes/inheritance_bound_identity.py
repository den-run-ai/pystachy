# Viewing one receiver through its base preserves bound-method identity and defining-method
# metadata. A virtual-call dispatcher is an implementation detail, not a different Python method.
from typing import Callable


class Base:
    def value(self, n: int) -> int:
        return n


class Child(Base):
    def value(self, n: int) -> int:
        return n + 1


class Grandchild(Child):
    pass


child = Child()
base: Base = child
print(base.value.__name__, base.value.__qualname__)
print(base.value == child.value, base.value == base.value, base.value != Child().value)
print(base.value(2), child.value(2))
grandchild = Grandchild()
as_base: Base = grandchild
print(as_base.value.__name__, as_base.value.__qualname__)
print(as_base.value == grandchild.value, as_base.value == base.value)
base_callback: Callable[[int], int] = base.value
child_callback: Callable[[int], int] = child.value
other_callback: Callable[[int], int] = Child().value
grand_callback: Callable[[int], int] = grandchild.value
print(base_callback == child_callback, base_callback != other_callback)
print(grand_callback == child_callback, base_callback(4), child_callback(4))
