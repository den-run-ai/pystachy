# Module constants that field_module_constants.py's fields are stored from
import sys
from typing import Final


class Capsule:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"Capsule({self.name!r})"


HAVE_IMMORTAL: Final = sys.version_info >= (3, 12)
WIDTH = 8
HEIGHT = WIDTH * 2
NAME: Final = "box"
RATIO = 0.5
STRINGS: Final = Capsule("librt.strings")
NAMES = ["a", "b"]
