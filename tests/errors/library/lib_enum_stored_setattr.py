# error: setattr() of ' enum int' on a Status, which does not have it, would add an attribute to the object, which is not supported (#489)
import sys
from enum import IntEnum


class Status(IntEnum):
    OK = 0


setattr(Status.OK, " enum int", 7)
sys.exit(Status.OK)
