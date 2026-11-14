# Without postponed evaluation, what CPython never evaluates may name what if TYPE_CHECKING:
# imports bind: quoted annotations (a nested def's too), a local variable's annotation and the
# value of a type statement
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tcpkg.class_ir import ClassIR

type MaybeClass = ClassIR | None


def first(classes: "list[ClassIR]") -> "MaybeClass":
    def name_of(c: "ClassIR") -> str:
        return c.name

    best: ClassIR | None = None
    for c in classes:
        if best is None or name_of(c) < name_of(best):
            best = c
    return best
