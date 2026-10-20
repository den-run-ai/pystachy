# error: calling Seq.__iter__() is not supported (its iterator is the list it steps through here): iterate over the object
from collections.abc import Iterator


class Seq:
    def __init__(self) -> None:
        self.xs = [1, 2]

    def __iter__(self) -> Iterator[int]:
        return iter(self.xs)


it = Seq().__iter__()
for x in it:
    break
print(list(it))
