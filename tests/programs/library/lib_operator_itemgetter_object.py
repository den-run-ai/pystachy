# itemgetter(i) of a variable i indexes a fixed tuple at run time: its result is one of the
# union of the items' types, which holds an object beside a number
from operator import itemgetter


class C:
    def __repr__(self) -> str:
        return "C()"


def f(i: int) -> "int | C":
    return itemgetter(i)((1, C()))


def g(i: int) -> str:
    item = (1, C(), "s")[i]
    if isinstance(item, C):
        return "object"
    return str(item)


print(f(0), f(1), g(0), g(1), g(2))
