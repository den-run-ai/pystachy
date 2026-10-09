"""A class whose __iter__ is a generator: an error only where the program iterates over one."""
from collections.abc import Iterator


class Lines:
    def __init__(self, text: str) -> None:
        self.text = text

    def __iter__(self) -> Iterator[str]:
        for line in self.text.splitlines():
            yield line

    def count(self) -> int:
        return len(self.text.splitlines())
