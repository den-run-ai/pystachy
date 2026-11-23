# error: unsupported type annotation
from typing import IO


def first(source: IO[bytes]) -> bytes:
    return source.read(1)


with open("/dev/null", "rb") as stream:
    print(first(stream))
