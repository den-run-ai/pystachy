import typing
from io import StringIO
from typing import IO as Stream, Optional


class Record:
    def __init__(self, source: Stream[str]) -> None:
        self.text = source.read().removeprefix("\ufeff")


def first(source: "typing.IO[str]") -> str:
    return source.read(1)


def remaining(source: Optional[Stream[str]]) -> str:
    return "missing" if source is None else source.read()


s = StringIO("\ufeffonetwo")
print(first(s) == "\ufeff", Record(s).text)
print(remaining(None), repr(remaining(s)))
s2 = StringIO("\ufeffpayload")
print(Record(s2).text, s2.tell())
with open("/dev/null") as file:
    print(repr(first(file)), repr(Record(file).text))
