# error: pick() returns both list and int (each function has one return type): its parameter 'flag' chooses which, and this call gives it no literal
# An empty list and an int join to no type: where the flag is no literal, both returns run.
import sys


def pick(flag):
    out = []
    if flag:
        return out
    return 5


print(pick(len(sys.argv) > 5))
