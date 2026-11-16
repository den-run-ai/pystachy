from adapter import TypedIterator


class PairCursor:
    def __init__(self, value: tuple[int, int]) -> None:
        self.value = value
        self.done = False

    def __iter__(self):
        return self

    def __next__(self) -> tuple[int, int]:
        if self.done:
            raise StopIteration
        self.done = True
        return self.value


def read_pair(source: TypedIterator[tuple[int, int]]) -> tuple[int, int]:
    return next(source)
