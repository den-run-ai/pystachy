# A template's function called before its module's code assigns a global it reads, whose value
# calls that same template (through an annotated function), or a global declared first.
import sys


def show(x):
    if x > 0:
        return str(x) + G
    return "g"


def helper(n: int) -> str:
    return show(n) + "h"


if len(sys.argv) > 5:
    print(show(1))
G = helper(0)
print(show(2))
H: str


def tell(x):
    if x > 0:
        return str(x) + H
    return "h"


if len(sys.argv) > 5:
    print(tell(1))
H = tell(0)
print(tell(2))
