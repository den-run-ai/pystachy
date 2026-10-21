from __future__ import annotations
from mods.alias_base import Box


def show(value: Crate) -> int:
    return value.v


def quoted(value: "Crate") -> int:
    return value.v + 1


# An annotation does not read the runtime alias; both calls work before it is bound.
print(show(Box(3)), quoted(Box(4)))
Crate = Box
print(show(Crate(5)), quoted(Crate(6)))
