# error: cannot send float to Generator[float], whose send type is None: annotate its generator function -> Generator[Y, S, R]
from collections.abc import Iterator


def averager() -> Iterator[float]:
    total = 0.0
    while True:
        yield total


g = averager()
for v in g:
    break
g.send(5.0)
