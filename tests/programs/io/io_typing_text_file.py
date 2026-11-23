from typing import IO


def read_one(source: IO[str]) -> str:
    return source.read(1)


with open("/dev/null") as source:
    print(repr(read_one(source)))
