# A class-body attribute annotated Final whose value is no constant (a list, dict or tuple display,
# an expression) takes its value's type, as an unannotated class attribute does (mypy's
# TypeInfo.FLAGS), here and in an imported module; its class has __annotations__.
from typing import Final

from final_attr_support.fattrs import Node, Sub


class Info:
    FLAGS: Final = ["is_abstract", "is_enum"]
    MAP: Final = {"a": 1, "b": 2}
    PAIR: Final = (1, "x")
    NEG: Final = -1
    BUF: Final = 2**16

    def __init__(self) -> None:
        self.is_abstract = True
        self.is_enum = False

    def set_flags(self) -> list[str]:
        return [f for f in self.FLAGS if f != "is_enum"]


class Plain:
    X: Final = [1, 2]


class Unannotated:
    X = [1, 2]


i = Info()
print(Info.FLAGS, i.FLAGS, Info.MAP["b"], i.set_flags(), Info.PAIR, Info.NEG, Info.BUF)
Info.FLAGS.append("is_final")
print(i.FLAGS, i.FLAGS is Info.FLAGS, len(Info.MAP) + Info.PAIR[0])
print(hasattr(i, "__annotations__"), hasattr(Plain(), "__annotations__"), hasattr(Unannotated(), "__annotations__"))
n = Node()
s = Sub()
print(Node.KINDS, n.KINDS, s.KINDS, s.describe(), Sub.TABLE["x"], s.TABLE["y"])
