# A callback's StopIteration is propagated unchanged, and need not exhaust an adapter.
class Restartable:
    def __init__(self):
        self.i = 0

    def __iter__(self):
        return self

    def __next__(self) -> int:
        self.i += 1
        if self.i == 2:
            raise StopIteration("pause")
        if self.i >= 5:
            raise ValueError("finished")
        return self.i


def mapper(x: int) -> int:
    if x == 2:
        raise StopIteration("callback")
    return x * 3


def predicate(x: int) -> bool:
    if x == 2:
        raise StopIteration("predicate")
    return True


z = zip(Restartable(), [10, 20, 30, 40])
print(next(z))
try:
    print(next(z))
except StopIteration as e:
    print("zip", str(e))
print(next(z), next(z))
try:
    print(next(z))
except ValueError as e:
    print("zip", str(e))
m = map(mapper, [1, 2, 3])
print(next(m))
try:
    print(next(m))
except StopIteration as e:
    print("map", str(e))
print(next(m), next(m, None))
f = filter(predicate, [1, 2, 3])
print(next(f))
try:
    print(next(f))
except StopIteration as e:
    print("filter", str(e))
print(next(f), next(f, None))
e = enumerate(Restartable(), 10)
print(next(e))
print(next(e, None), next(e))
