# error: a generator function's return annotation must be Iterator[T], Iterable[T] or Generator[Y, S, R]
def nums() -> list[int]:
    yield 1


print(nums())
