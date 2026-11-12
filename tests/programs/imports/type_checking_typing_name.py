# The main module's if TYPE_CHECKING: imports name classes for its annotations too (Label), but a
# name that typing offers as well (Callable) keeps typing's meaning there, as it has without that
# import: CPython evaluates none of these annotations. Another name for such a class (ShadowType)
# names the class.
from __future__ import annotations

from typing import TYPE_CHECKING

import tcpkg.shadow

if TYPE_CHECKING:
    from tcpkg.shadow import Callable, Label
    from tcpkg.shadow import Type as ShadowType


def run(c: Callable[[int], int]) -> int:
    return c(1)


def name(t: ShadowType) -> str:
    return t.name


def text(label: Label) -> str:
    return label.text.upper()


print(run(lambda x: x + 1), name(tcpkg.shadow.Type("int")), text(tcpkg.shadow.Label("ok")))
print(tcpkg.shadow.Callable(2).n)
