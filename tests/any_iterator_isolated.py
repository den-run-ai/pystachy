# Keep this program isolated: another iter() call would hide its helper dependency.
from typing import Any, Iterator


class Values:
    def __iter__(self) -> Iterator[Any]:
        return iter([1, 2])


print(list(Values()))
