# _value_ is mutable enum metadata, independent of CPython's immutable integer payload.
import sys
from enum import IntEnum


class Status(IntEnum):
    FAILED = 3
    ALIAS = 3


Status.ALIAS._value_ = 9
print(Status.FAILED.value, Status.ALIAS is Status.FAILED, flush=True)
sys.exit(Status.ALIAS)
