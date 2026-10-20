# error: 'Steps' object is not iterable
# (CPython: TypeError, as for x in o.items() takes iter() of what items() returns, an object
# whose class defines __next__ but no __iter__)
class Steps:
    def __init__(self) -> None:
        self.k = 0

    def __next__(self) -> int:
        self.k += 1
        if self.k > 2:
            raise StopIteration
        return self.k


class Store:
    def items(self) -> Steps:
        return Steps()


for x in Store().items():
    print(x)
