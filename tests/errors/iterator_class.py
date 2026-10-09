# error: iterator_class.py:16: error: an iterator class is not supported: Count.__iter__ returns a Count, whose __next__ CPython would call until it raises StopIteration; return iter(xs) of a list xs of the items (-> Iterator[T])
class Count:
    def __init__(self) -> None:
        self.i = 0

    def __iter__(self) -> "Count":
        return self

    def __next__(self) -> int:
        if self.i >= 2:
            raise StopIteration
        self.i += 1
        return self.i


for v in Count():
    print(v)
