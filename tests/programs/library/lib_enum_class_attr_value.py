from enum import Flag

from enum_palette import Color as Ink
import enum_palette


class Permission(Flag):
    READ = 1
    WRITE = 2
    R = READ


class Palette:
    kind = Ink
    scale = enum_palette.Weight


class DarkPalette(Palette):
    pass


class Access:
    kind = Permission


def lookup(schema, key: str) -> str | None:
    return schema.kind[key].name


print(Palette.kind.RED, DarkPalette.kind is Ink, Palette().scale.HEAVY + 1)
print(lookup(DarkPalette(), "GREEN"), lookup(Access(), "R"))
print(Access.kind.READ | Access().kind.WRITE, Access.kind.R is Permission.READ)
print([x.value for x in DarkPalette.kind], Palette().kind("g") is Ink.GREEN)
