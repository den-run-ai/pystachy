# sys.exit() of an IntEnum member in a program without try: CPython's member is an int, the
# exit status, and nothing is written to stderr.
import sys
from enum import IntEnum


class Status(IntEnum):
    OK = 0
    USAGE = 3


print("bye", flush=True)
sys.exit(Status.USAGE)
