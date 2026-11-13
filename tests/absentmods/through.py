# A module that imports one whose import of a missing module fails: it fails there as well.
print("through: before the import")
import absentmods.needs_c
print("through: not reached")


def low() -> int:
    return absentmods.needs_c.Level.LOW
