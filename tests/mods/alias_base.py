"""A function and a class, from-imported and aliased by mods.alias_mid (tests/programs/imports/import_alias_reexport.py)."""


def inc(x: int) -> int:
    return x + 1


class Box:
    def __init__(self, v: int) -> None:
        self.v = v
