# A member seen through Enum keeps its integer status, including C exit-code truncation.
import sys
from enum import Enum, IntEnum


class Status(IntEnum):
    FAILED = 293

    def __index__(self) -> int:
        print("unexpected index", flush=True)
        return 0

    def __int__(self) -> int:
        print("unexpected int", flush=True)
        return 0

    def __str__(self) -> str:
        return "custom status text"


def status() -> Enum:
    return Status.FAILED


print("base view", flush=True)
sys.exit(status())
