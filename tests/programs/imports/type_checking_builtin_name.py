# A name that an if TYPE_CHECKING: import binds and that the builtins offer too (int) keeps the
# builtin's meaning in annotations, as it has without that import: CPython evaluates neither
# annotation here.
from __future__ import annotations

from typing import TYPE_CHECKING

import tcpkg.builtin_names

if TYPE_CHECKING:
    from tcpkg.builtin_names import int


def twice(x: int) -> int:
    return x + x


print(twice(3), tcpkg.builtin_names.int("text").text)
