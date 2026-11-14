# A module's if NAME: or if not NAME: right after NAME = True or NAME = False, as mypy's
# MYPYC = False switch, is decided at compile time where the branch that does not run only
# assigns names that the branch that runs binds too: that branch is never compiled (Missing is
# defined nowhere), and its names keep the types of the branch that runs (Kind is a str, Level a
# float). The flag stays an ordinary global, which code may read and assign later.
MYPYC = False
if MYPYC:
    Kind = Missing
    Size = Kind
else:
    Kind = "native"
    Size = 4

DEBUG = True
if not DEBUG:
    pass
    Level = Missing
else:
    Level = 2.5

COMPACT = True
if COMPACT:
    Width, Height = 3, 7
else:
    Width = Height = Missing


def show() -> str:
    return Kind.upper() + " " + str(Size + 1) + " " + str(Level * 2) + " " + str(Width * Height)


def flag() -> bool:
    return MYPYC


print(show(), flag(), DEBUG, COMPACT)
MYPYC = True
print(flag())
