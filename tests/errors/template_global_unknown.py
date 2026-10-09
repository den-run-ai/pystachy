# error: the type of 'W' is not known yet here, before its module's code assigns it: declare it at module level first (W: T)
import sys


def show(x):
    return str(x) + str(W)


if len(sys.argv) > 3:
    print(show(1))
for W in range(2):
    pass
print(show(2))
