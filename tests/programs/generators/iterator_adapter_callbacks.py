# Construction evaluates all arguments before making iterators, then steps in order.
class Cursor:
    def __init__(self, label: str, stop: int):
        self.label = label
        self.stop = stop
        self.i = 0

    def __iter__(self):
        print("iter", self.label)
        return self

    def __next__(self) -> int:
        self.i += 1
        print("next", self.label, self.i)
        if self.i > self.stop:
            raise StopIteration
        return self.i


def make(label: str, stop: int) -> Cursor:
    print("make", label)
    return Cursor(label, stop)


def mapped(value: int) -> int:
    print("map", value)
    return value * 10


def predicate(value: int) -> bool:
    print("filter", value)
    return value == 2


z = zip(make("a", 3), make("b", 1))
print("created zip")
print(next(z))
print(next(z, None))
print(next(z, None))
e = enumerate(make("e", 2), start=4)
print("created enumerate")
print(next(e), next(e), next(e, None))
m = map(mapped, make("m", 2))
print("created map")
print(next(m), list(m))
f = filter(predicate, make("f", 3))
print("created filter")
print(next(f), list(f))
