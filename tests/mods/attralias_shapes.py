# Classes that other modules alias through this module's attributes
# (tests/programs/imports/import_attr_class_alias.py)
class Box:
    kind = "box"

    def __init__(self, v: int) -> None:
        self.v = v


class Crate(Box):
    kind = "crate"

    def __init__(self, v: int) -> None:
        super().__init__(v * 10)


class Oops(Exception):
    pass


class Missing:
    def __repr__(self) -> str:
        return "<missing>"


Missing = Missing()
