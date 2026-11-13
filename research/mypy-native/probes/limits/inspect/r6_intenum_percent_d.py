# %d of an IntEnum member, which is an int in CPython
import enum

class Kind(enum.IntEnum):
    A = 3

print("%d" % Kind.A)
