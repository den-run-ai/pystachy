# A module that needs a C module nobody has: CPython raises ModuleNotFoundError at the import, and
# the statements after it never run (tests/programs/optional/optional_missing_nested.py).
from enum import IntEnum

print("needs_c: before the import")
import _pystachy_absent_c
print("needs_c: not reached")


class Level(IntEnum):
    LOW = _pystachy_absent_c.LOW
    HIGH = _pystachy_absent_c.HIGH


def version() -> str:
    return _pystachy_absent_c.version()
