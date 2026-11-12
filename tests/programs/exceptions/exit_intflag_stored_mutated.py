# Computed and aliased IntFlag members retain the integer supplied at their creation.
import sys
from enum import Enum, IntFlag


class Perm(IntFlag):
    READ = 4
    ALIAS = 4
    WRITE = 2

    def __index__(self) -> int:
        print("unexpected index", flush=True)
        return 0

    def __int__(self) -> int:
        print("unexpected int", flush=True)
        return 0

    def __str__(self) -> str:
        return "custom permissions"


def as_enum(value: Perm) -> Enum:
    return value


combined = Perm.ALIAS | Perm.WRITE
combined._value_ = 9
Perm.ALIAS._value_ = 8
print(combined.value, Perm.READ.value, Perm.READ is Perm.ALIAS, flush=True)
sys.exit(as_enum(combined))
