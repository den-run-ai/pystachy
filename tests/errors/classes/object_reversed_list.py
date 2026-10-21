# error: Seq.__reversed__ returning list[int] is not supported: return iter(xs) of a list xs of the items (-> Iterator[T])
# CPython iterates over the list that __reversed__ returns; here it returns an iterator
class Seq:
    def __init__(self) -> None:
        self.xs = [1, 2]

    def __reversed__(self) -> list[int]:
        return self.xs[::-1]


for x in reversed(Seq()):
    print(x)
