# A zero-valued alias keeps its status despite integer and string conversion overrides.
import sys
from enum import IntEnum


class Status(IntEnum):
    OK = 0
    SUCCESS = 0

    def __index__(self) -> int:
        print("unexpected index", flush=True)
        return 7

    def __int__(self) -> int:
        print("unexpected int", flush=True)
        return 8

    def __str__(self) -> str:
        return "wrong message"


print(Status.SUCCESS is Status.OK, flush=True)
sys.exit(Status.SUCCESS)
