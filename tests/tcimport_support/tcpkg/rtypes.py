# Annotations that name classes imported only under if TYPE_CHECKING: (a circular import:
# class_ir imports this module), in each import form
from __future__ import annotations

import typing
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import tcpkg.class_ir as cmod
    from tcpkg.class_ir import ClassIR

if typing.TYPE_CHECKING:
    from .class_ir import FuncIR as Func

last: ClassIR | None = None


class RInstance:
    def __init__(self, class_ir: ClassIR) -> None:
        self.class_ir = class_ir
        self.name = class_ir.name

    def attr_type(self, attr: str) -> str:
        return self.class_ir.attr_type(attr)

    def owner(self) -> "ClassIR":
        return self.class_ir

    def same(self, other: cmod.ClassIR | None) -> bool:
        return other is self.class_ir


def methods(cls: ClassIR, funcs: list[Func]) -> list[str]:
    return [cls.name + "." + f.name for f in funcs]


def remember(cls: ClassIR) -> None:
    global last
    last = cls
