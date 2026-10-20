# An empty container that from m import X copies, read before the importer fills it: a read of
# m.X takes its type from the fill of X further on, and so does a template's function that
# reads X, compiled before the from-import runs (as for an alias Y = X of the module's own).
import sys
import infer.twin


def show(x):
    return str(x) + str(BOX) + str(len(ALIAS))


if len(sys.argv) > 3:
    print(show(1))
from infer.twin import REG, BOX

print(infer.twin.REG)
REG["k"] = [1]
print(REG, infer.twin.REG)
BASE = []
ALIAS = BASE
ALIAS.append(1)
BOX["a"] = 1
print(show(2), BASE, infer.twin.BOX)
