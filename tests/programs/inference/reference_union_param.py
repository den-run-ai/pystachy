# A parameter annotated with a union of a class and a str or number, which no one type holds,
# is typed by each call's argument.
from pathlib import Path


class Stream:
    def __init__(self, name: str) -> None:
        self.name = name


def show(value: Stream | int) -> str:
    if isinstance(value, Stream):
        return "stream " + value.name
    return "int " + str(value + 1)


def name_of(filename: str | Path) -> str:
    return Path(filename).name


print(show(Stream("s")), show(41), name_of("a/b.txt"), name_of(Path("c/d.json")))
