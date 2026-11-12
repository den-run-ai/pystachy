# pystachy: dynamic-any
from typing import Callable


class PropertyArgs(Exception):
    @property
    def args(self) -> tuple[int, int]:
        print("args property")
        return (7, 8)


class InheritedArgs(PropertyArgs):
    pass


class PlainArgs(Exception):
    pass


class ChildArgs(PlainArgs):
    @property
    def args(self) -> tuple[int, int]:
        return (12, 13)


class MethodArgs(Exception):
    def args(self) -> str:
        return "args method"


class PropertyValue(StopIteration):
    @property
    def value(self) -> int:
        print("value property")
        return 42


class MethodValue(StopIteration):
    def value(self) -> str:
        return "value method"


print(PropertyArgs(1).args)
print(InheritedArgs(2).args)
try:
    raise PropertyArgs(3)
except PropertyArgs as error:
    print(error.args)
args: Callable[[], str] = MethodArgs(4).args
print(args(), MethodArgs(5).args())
print(PropertyValue(6).value)
try:
    raise PropertyValue(7)
except PropertyValue as error:
    print(error.value)
value: Callable[[], str] = MethodValue(8).value
print(value(), MethodValue(9).value())

# Direct source overrides above do not change inherited builtin descriptors.
print(ValueError(10).args, StopIteration(11).value)
print(PlainArgs(14).args, ChildArgs(15).args)
