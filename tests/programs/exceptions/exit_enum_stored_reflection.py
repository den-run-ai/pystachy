import sys
from enum import Enum, IntEnum, IntFlag


class Status(IntEnum):
    OK = 0
    ALIAS = 0


class Perm(IntFlag):
    READ = 1
    WRITE = 2


def default():
    print("default")
    return 37


def probe(value: Enum, name: str):
    print(hasattr(value, " enum int"))
    print(getattr(value, " enum int", default()))
    print(hasattr(value, name))


# Declared members, aliases, computed flag members and base-typed views all
# retain the reflection result from before the private payload was added.
print(hasattr(Status.OK, " enum int"), getattr(Status.OK, " enum int", 99))
print(hasattr(Perm(0), " enum int"), getattr(Perm(0), " enum int", 99))
probe(Status.ALIAS, " enum int")
probe(Perm(0), " enum int")
probe(Perm.READ | Perm.WRITE, " enum int")
sys.exit(Status.OK)
