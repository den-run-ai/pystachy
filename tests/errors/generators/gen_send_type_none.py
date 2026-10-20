# error: a generator's send type must be one that may be None (next() sends None), not file
from collections.abc import Generator
from typing import TextIO


def acc() -> Generator[int, TextIO, None]:
    e = yield 1
    print(e)


for v in acc():
    print(v)
