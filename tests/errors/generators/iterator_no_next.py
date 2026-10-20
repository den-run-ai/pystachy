# error: iter() returned non-iterator of type 'Loop'
# (CPython: TypeError, once __iter__ has returned an object whose class has no __next__)
class Loop:
    def __iter__(self) -> "Loop":
        return self


for x in Loop():
    print(x)
