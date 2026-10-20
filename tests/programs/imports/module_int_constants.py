# Int-literal reads preserve rebinding, from-import snapshots and initialization order.
import mods.intconstants as source
import mods.intconstants_copy as copied
from mods.intconstants import STABLE as TAKEN, REBOUND as SNAPSHOT
from mods.intconstants_copy import STABLE as CHAIN

POSITIVE = +19
NEGATIVE = -20
MINIMUM = -9223372036854775808
ANNOTATED: int = 21


def literals() -> tuple[int, int, int, int]:
    return POSITIVE, NEGATIVE, MINIMUM, ANNOTATED


def shadow(POSITIVE: int) -> int:
    return POSITIVE


print(literals(), shadow(22))
print(source.values(), source.late(), copied.copied_values(), TAKEN, SNAPSHOT, CHAIN)
source.REBOUND = 23
copied.STABLE = 24
print(source.values(), copied.copied_values(), TAKEN, SNAPSHOT, CHAIN)

REASSIGNED = 25
AUGMENTED = 26
GLOBAL = 27
LOOP = 28
DELETED = 29
CONDITIONAL = 30


def globals_now() -> tuple[int, int, int, int, int]:
    return REASSIGNED, AUGMENTED, GLOBAL, LOOP, CONDITIONAL


def update() -> None:
    global GLOBAL
    GLOBAL = 31


print(globals_now())
REASSIGNED = 32
AUGMENTED += 7
update()
for LOOP in [34]:
    pass
if shadow(1):
    CONDITIONAL = 35
del DELETED
print(globals_now())
try:
    print(DELETED)
except NameError:
    print("deleted")


def late() -> int:
    return LATE


try:
    print(late())
except NameError:
    print("late unbound")
LATE = 36
print(late())

from mods import intconstants_cycle_a
print(intconstants_cycle_a.late())
