# error: next() of Count, whose __next__ returns int, with a default of str is not supported (each call has one type)
class Count:
    def __init__(self) -> None:
        self.i = 0

    def __iter__(self) -> "Count":
        return self

    def __next__(self) -> int:
        self.i += 1
        if self.i > 2:
            raise StopIteration
        return self.i


print(next(Count(), "none"))
