# A list annotated with a Protocol converts each appended or assigned item.
from typing import Iterator, Protocol


class Stream(Protocol):
    def __next__(self) -> int: ...


def gen() -> Iterator[int]:
    yield 3


streams: list[Stream] = []
streams.append(iter([1, 2]))
streams.append(gen())
streams.insert(0, iter((7,)))
print([next(s) for s in streams])
streams[1] = gen()
print(next(streams[1]), len(streams))
