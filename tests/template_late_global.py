# A template's function compiled before its module's code assigns a global it reads (the
# template is called first in a branch that does not run): the global's first assignment gives
# it its type there (an empty container's, as the code or a function that fills it shows), and
# the read is checked when it runs. So does a read in module code before the assignment, in a
# loop.
import sys


def show(x):
    return str(x) + SUFFIX


if len(sys.argv) > 3:
    print(show(1))
SUFFIX = "!"
print(show(2))


class Config:
    def __init__(self, name: str):
        self.name = name


def make() -> int:
    return 41


def mk(n):
    return [n] * n


def describe(x):
    return f"{x} {TABLE} {len(NAMES)} {PREFIX} {B} {CFG.name} {LATE} {ITEMS} {Q} {S}"


def first() -> str:
    return describe(0)


if len(sys.argv) > 3:
    print(first())
TABLE = {"a": 1}
NAMES = [1, 2]
PREFIX = "<" * 2
A = make()
B = A + 1
CFG = Config("cfg")
LATE: float = 2.5
ITEMS = []
ITEMS.append(3)
Q = mk(3)
if len(sys.argv) > 1:
    S = "yes"
else:
    S = "no"
print(describe(1))
print(first())


def tags(x):
    return str(x) + str(TAGS)


def tag(v: str) -> None:
    TAGS.append(v)


if len(sys.argv) > 3:
    print(tags(1))
TAGS = []
tag("q")
print(tags(2))

for i in range(3):
    if i > 0:
        print("last", last)
    last = i
