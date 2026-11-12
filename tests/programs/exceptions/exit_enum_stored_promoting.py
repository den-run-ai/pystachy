# pystachy: python-int
# A supported wide enum value keeps its integer payload in a module whose ints can promote.
import sys
from enum import IntEnum


class Status(IntEnum):
    WIDE = 4611686018427387907

    def __index__(self) -> int:
        print("unexpected index", flush=True)
        return 0

    def __int__(self) -> int:
        print("unexpected int", flush=True)
        return 0


Status.WIDE._value_ = 7
print(Status.WIDE.value, flush=True)
sys.exit(Status.WIDE)
