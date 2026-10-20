from typing import Any, Iterator

Items = list[Any]


class Values:
    def __iter__(self) -> Iterator[Items]:
        return iter([[1, 2], [3]])


print(list(Values()))
