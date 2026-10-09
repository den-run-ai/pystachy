# error: the type of 'late' is not known yet here, before its module's code assigns it: declare it at module level in tests/errors/emods/late_setter.py first (late: T)
import sys
import emods.late_setter


def show(x):
    return str(x) + str(late)


if len(sys.argv) > 3:
    print(show(1))
if len(sys.argv) > 5:
    emods.late_setter.setup()
from emods.late_setter import late

print(show(2))
