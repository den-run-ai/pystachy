# x: ClassVar[T] = v in an ordinary class is the class attribute x: T = v: counters and tables
# that the class's methods update through the class (mypy's TypeVarId.next_raw_id, mypyc's
# RPrimitive.primitive_map), read through objects and subclasses, here and in an imported module.
import typing
from typing import ClassVar

from final_attr_support.cvattrs import Counter


class TypeVarId:
    next_raw_id: ClassVar[int] = 1
    kinds: typing.ClassVar[list[str]] = ["raw"]

    def __init__(self, raw_id: int) -> None:
        self.raw_id = raw_id

    @staticmethod
    def new() -> "TypeVarId":
        raw_id = TypeVarId.next_raw_id
        TypeVarId.next_raw_id += 1
        return TypeVarId(raw_id)


class Primitive:
    primitive_map: ClassVar[dict[str, "Primitive"]] = {}

    def __init__(self, name: str) -> None:
        self.name = name
        Primitive.primitive_map[name] = self


class Native(Primitive):
    pass


a = TypeVarId.new()
b = TypeVarId.new()
print(a.raw_id, b.raw_id, TypeVarId.next_raw_id, a.next_raw_id, b.kinds)
Primitive("builtins.int")
Native("librt.Lock")
print(sorted(Primitive.primitive_map), Native.primitive_map["librt.Lock"].name)
print(hasattr(a, "__annotations__"), Primitive.primitive_map is Native.primitive_map)
c = Counter("x")
d = Counter("y")
print(c.id, d.id, Counter.next_id, sorted(Counter.names.items()))
