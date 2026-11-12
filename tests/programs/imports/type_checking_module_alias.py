# import pkg.mod as pkg under if TYPE_CHECKING: binds the module pkg.mod to the name pkg, for
# annotations (tcpkg.ClassIR), as CPython would if it ran the import.
from __future__ import annotations

from typing import TYPE_CHECKING

from tcpkg.class_ir import ClassIR

if TYPE_CHECKING:
    import tcpkg.class_ir as tcpkg


def name(c: tcpkg.ClassIR) -> str:
    return c.name


print(name(ClassIR("C")))
