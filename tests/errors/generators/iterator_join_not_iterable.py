# error: 'Steps' object is not iterable
# str.join() makes a list of the items of iter(o), which takes iter() of that iterator again
# (CPython's PySequence_Fast): an iterator class without __iter__ is a TypeError there
class Steps:
    def __init__(self) -> None:
        self.k = 0

    def __next__(self) -> str:
        self.k += 1
        if self.k > 2:
            raise StopIteration
        return str(self.k)


class Holder:
    def __iter__(self) -> Steps:
        return Steps()


for s in Holder():
    print(s)
print(", ".join(Holder()))
