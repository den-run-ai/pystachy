# error: the type of 'G' is not known yet here, before its module's code assigns it: declare it at module level first (G: T)
import sys


def show(x):
    if x > 0:
        return str(x) + G
    return "g"


if len(sys.argv) > 5:
    print(show(1))
G = show(0)
print(show(2))
