from __future__ import annotations

from mods.anyvars import read, values

TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import Any

value: Any = 4


def local() -> int:
    xs: list[Any] = []
    xs.append(value)
    return xs[0]


print(local(), read(), values)
