# pystachy: dynamic-any
# Constant-global reads retain cached, literal and from-import identity.
from typing import Any
import mods.dynidentity_constants as source
from mods.dynidentity_constants import SMALL as IMPORTED_SMALL, LARGE as IMPORTED_LARGE

SMALL = 17
LARGE = 1000
NEGATIVE = -1000


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


def read_late() -> Any:
    return LATE


same("cached", SMALL, source.SMALL)
same("cached import", IMPORTED_SMALL, source.SMALL)
same("large import", IMPORTED_LARGE, source.LARGE)
same("distinct modules", LARGE, source.LARGE)
same("negative modules", NEGATIVE, source.NEGATIVE)
same("same module literal", LARGE, 1000)
try:
    print(read_late())
except NameError:
    print("late unbound")
LATE = 18
same("late initialized", read_late(), LATE)
