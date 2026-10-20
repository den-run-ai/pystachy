# error: 'Steps' object is not iterable
# a comprehension takes iter() of its iterable's iterator again, as CPython 3.13's does: an
# iterator class without __iter__ is a TypeError there (a for statement takes it once)
class Steps:
    def __init__(self) -> None:
        self.k = 0

    def __next__(self) -> int:
        self.k += 1
        if self.k > 2:
            raise StopIteration
        return self.k


class Holder:
    def __iter__(self) -> Steps:
        return Steps()


print([x for x in Holder()])
