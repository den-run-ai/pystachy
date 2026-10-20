# error: indexing a tuple[int,C] with a variable index is not supported: reference unions cannot mix native references with scalar or container members
# itemgetter(i) of a variable i indexes a fixed tuple at run time, which needs a union of its
# items' types
from operator import itemgetter


class C:
    pass


def f(i: int) -> int:
    return itemgetter(i)((1, C()))


print(f(0))
