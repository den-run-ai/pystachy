# IntFlag's computed zero is an integer status; custom conversion methods do not decide it.
import sys
from enum import IntFlag


class Perm(IntFlag):
    READ = 4
    WRITE = 2

    def __index__(self) -> int:
        print("unexpected index", flush=True)
        return 7

    def __int__(self) -> int:
        print("unexpected int", flush=True)
        return 8

    def __str__(self) -> str:
        return "custom zero"


zero = Perm(0)
zero._value_ = 9
print(zero.value, flush=True)
sys.exit(zero)
