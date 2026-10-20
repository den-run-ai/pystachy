# A template's function that reads a global before its module's code assigns it raises
# NameError there, as in CPython.
import sys


def show(x):
    return str(x) + SUFFIX


print("start")
if len(sys.argv) > 2:
    print(show(1))
SUFFIX = "!"
print(show(2))
