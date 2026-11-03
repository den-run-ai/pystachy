# enum classes of another module, for tests/programs/library/lib_enum_import.py and
# tests/errors/library/lib_enum_other_module_base.py
import enum


class Color(enum.Enum):
    RED = "r"
    GREEN = "g"

    @property
    def label(self) -> str:
        return self.name.lower()

    @classmethod
    def default(cls) -> "Color":
        return Color.GREEN


class Weight(enum.IntEnum):
    LIGHT = 1
    HEAVY = 10


class Shade(enum.Enum):
    # (without members: an enum class of this module may derive from it)
    def describe(self) -> str:
        return "<" + self.name + ">"
