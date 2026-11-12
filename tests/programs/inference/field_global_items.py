# A field stored from a module global that one annotated assignment binds (x: T = v, also
# x: Final[T] = v) takes T, and one stored from an item of it the item's type: a value of a
# dict, an item of a list, a str. As mypyc's RVec.buf_type = vec_buf_types[item_type], the
# globals may be bound further down, before the objects are made.
from typing import Final


class RType:
    def __init__(self, name: str) -> None:
        self.name = name


class RStruct(RType):
    def __init__(self, name: str, names: list[str]) -> None:
        super().__init__(name)
        self.names = names


class RVec(RType):
    def __init__(self, item_type: RType) -> None:
        super().__init__("vec")
        self.item_type = item_type
        if item_type in vec_buf_types:
            self.buf_type = vec_buf_types[item_type]
        else:
            self.buf_type = default_buf
        self.prefix = PREFIXES[0]
        self.letter = NAME[0]
        self.size = SIZES["vec"]
        self.table = vec_buf_types


int64_rprimitive = RType("int64")
default_buf = RStruct("VecTBufObject", ["ob_base", "items"])
vec_buf_types: Final[dict[RType, RStruct]] = {
    int64_rprimitive: RStruct("VecI64BufObject", ["len"]),
}
PREFIXES: list[str] = ["Vec", "Buf"]
NAME: Final[str] = "vec"
SIZES: dict[str, int] = {"vec": 16}

v = RVec(int64_rprimitive)
w = RVec(RType("str"))
print(v.buf_type.name, v.buf_type.names, w.buf_type.name, w.buf_type.names)
print(v.prefix + v.letter, v.size + 1, len(v.table))
